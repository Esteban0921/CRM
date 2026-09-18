import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from audit import record_field_changes
from billing import (
    invoice_amount,
    invoice_is_due_soon,
    invoice_is_outstanding,
    invoice_is_overdue,
    promote_overdue_invoices,
    unbilled_by_family,
)
from db import get_db
from dependencies import ensure_family_access, get_current_user, require_role
from models.audit_log import AuditedEntityType, AuditLog
from models.contract import Contract
from models.family import Family, FamilyStatus
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.note import Note, NoteEntityType
from models.student import Student, StudentStatus
from models.user import User, UserRole
from schemas.billing import FamilyBilling
from schemas.contract import ContractRead
from schemas.family import FamilyCreate, FamilyRead, FamilyUpdate
from schemas.family_invoice import FamilyInvoiceRead
from schemas.search import ActivityEvent
from schemas.student import StudentRead

router = APIRouter(prefix="/families", tags=["families"])


@router.post("", response_model=FamilyRead, status_code=status.HTTP_201_CREATED)
def create_family(
    payload: FamilyCreate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Family:
    family = Family(**payload.model_dump())
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


@router.get("", response_model=list[FamilyRead])
def list_families(
    q: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[FamilyRead]:
    """TASK-0075. El listado lleva deuda y hueco del mes para no ir ficha a ficha."""
    promote_overdue_invoices(db)
    query = db.query(Family)
    if q and len(q.strip()) >= 2:
        cleaned = "".join(ch for ch in q.strip() if ch not in "%_")
        query = query.filter(Family.name.ilike(f"%{cleaned}%"))
    families = query.order_by(Family.name).all()
    outstanding: dict = defaultdict(lambda: Decimal("0.00"))
    overdue: dict = defaultdict(lambda: Decimal("0.00"))
    for invoice in db.query(FamilyInvoice).filter(FamilyInvoice.family_id.isnot(None)).all():
        if invoice_is_outstanding(invoice):
            outstanding[invoice.family_id] += invoice_amount(invoice)
        if invoice_is_overdue(invoice):
            overdue[invoice.family_id] += invoice_amount(invoice)
    gaps = unbilled_by_family(db)
    return [
        FamilyRead.model_validate(family).model_copy(
            update={
                "outstanding_amount": outstanding[family.id],
                "overdue_amount": overdue[family.id],
                "unbilled": family.id in gaps,
            }
        )
        for family in families
    ]


@router.get("/{family_id}", response_model=FamilyRead)
def get_family(
    family_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Family:
    ensure_family_access(user, family_id)
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Familia no encontrada")
    return family


@router.get("/{family_id}/billing", response_model=FamilyBilling)
def get_family_billing(
    family_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FamilyBilling:
    """Deuda de una familia. El padre solo ve la suya (RULE-005)."""
    promote_overdue_invoices(db)
    ensure_family_access(user, family_id)
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Familia no encontrada")

    invoices = db.query(FamilyInvoice).filter(FamilyInvoice.family_id == family_id).all()
    if user.role == UserRole.PARENT:
        invoices = [i for i in invoices if i.status != FamilyInvoiceStatus.PENDING_REVIEW]
    outstanding = [i for i in invoices if invoice_is_outstanding(i)]
    overdue = [i for i in invoices if invoice_is_overdue(i)]
    due_soon = [i for i in invoices if invoice_is_due_soon(i)]
    return FamilyBilling(
        outstanding_amount=sum((invoice_amount(i) for i in outstanding), Decimal("0.00")),
        overdue_amount=sum((invoice_amount(i) for i in overdue), Decimal("0.00")),
        overdue_count=len(overdue),
        sent_count=sum(1 for i in invoices if i.status == FamilyInvoiceStatus.SENT),
        paid_count=sum(1 for i in invoices if i.status == FamilyInvoiceStatus.PAID),
        due_soon_count=len(due_soon),
        due_soon_amount=sum((invoice_amount(i) for i in due_soon), Decimal("0.00")),
    )


_FIELD_LABELS = {
    "name": "nombre",
    "address": "direccion",
    "status": "estado",
    "school": "colegio",
    "birth_date": "fecha de nacimiento",
    "family_id": "familia",
    "amount": "importe",
    "due_date": "vencimiento",
    "issue_date": "emision",
    "service_type": "servicio",
    "monthly_fee": "cuota",
}

_ENTITY_LABELS = {
    AuditedEntityType.FAMILY: "Familia",
    AuditedEntityType.STUDENT: "Alumno",
    AuditedEntityType.CONTRACT: "Contrato",
    AuditedEntityType.FAMILY_INVOICE: "Factura",
    AuditedEntityType.SUPPLIER_INVOICE: "Factura de proveedor",
}


@router.get("/{family_id}/activity", response_model=list[ActivityEvent])
def get_family_activity(
    family_id: uuid.UUID,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[ActivityEvent]:
    """TASK-0056. Historial interno: audit trail y notas. Nunca para el padre."""
    _ = staff
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Familia no encontrada")

    students = db.query(Student).filter(Student.family_id == family_id).all()
    student_ids = [student.id for student in students]
    contracts = (
        db.query(Contract).filter(Contract.student_id.in_(student_ids)).all() if student_ids else []
    )
    invoices = db.query(FamilyInvoice).filter(FamilyInvoice.family_id == family_id).all()

    events: list[ActivityEvent] = []
    audit_filters = [(AuditedEntityType.FAMILY, [family_id])]
    if student_ids:
        audit_filters.append((AuditedEntityType.STUDENT, student_ids))
    if contracts:
        audit_filters.append((AuditedEntityType.CONTRACT, [c.id for c in contracts]))
    if invoices:
        audit_filters.append((AuditedEntityType.FAMILY_INVOICE, [i.id for i in invoices]))

    logs: list[AuditLog] = []
    for entity_type, ids in audit_filters:
        logs.extend(
            db.query(AuditLog)
            .filter(AuditLog.entity_type == entity_type, AuditLog.entity_id.in_(ids))
            .all()
        )

    actor_ids = {log.edited_by for log in logs}
    notes = (
        db.query(Note)
        .filter(Note.entity_type == NoteEntityType.FAMILY, Note.entity_id == family_id)
        .all()
    )
    if student_ids:
        notes.extend(
            db.query(Note)
            .filter(Note.entity_type == NoteEntityType.STUDENT, Note.entity_id.in_(student_ids))
            .all()
        )
    actor_ids.update(note.created_by for note in notes)
    names = (
        dict(db.query(User.id, User.name).filter(User.id.in_(actor_ids)).all()) if actor_ids else {}
    )

    for log in logs:
        field = _FIELD_LABELS.get(log.field_name, log.field_name)
        entity = _ENTITY_LABELS.get(log.entity_type, log.entity_type.value)
        events.append(
            ActivityEvent(
                at=log.edited_at,
                kind="audit",
                title=f"{entity}: {field}",
                detail=f"{log.old_value or '—'} → {log.new_value or '—'}",
                actor_name=names.get(log.edited_by),
            )
        )
    for note in notes:
        events.append(
            ActivityEvent(
                at=note.created_at,
                kind="note",
                title="Nota interna",
                detail=note.body,
                actor_name=names.get(note.created_by),
            )
        )
    events.sort(key=lambda event: event.at, reverse=True)
    return events[:100]


@router.patch("/{family_id}", response_model=FamilyRead)
def update_family(
    family_id: uuid.UUID,
    payload: FamilyUpdate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Family:
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Familia no encontrada")
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(family, field) for field in changes}
    for field, value in changes.items():
        setattr(family, field, value)
    record_field_changes(
        db,
        entity_type=AuditedEntityType.FAMILY,
        entity_id=family.id,
        editor_id=staff.id,
        before=before,
        after=changes,
    )
    db.commit()
    db.refresh(family)
    return family


@router.get("/{family_id}/export")
def export_family_data(
    family_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """TASK-0012 (derecho de acceso/portabilidad, RGPD). Un padre puede
    exportar los datos de su propia familia; staff/admin, los de cualquiera.
    La política de retención (cuánto se guarda, cuándo se anonimiza de
    oficio) sigue sin decidir — esto es solo el mecanismo.
    """
    ensure_family_access(user, family_id)
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Familia no encontrada")

    students = db.query(Student).filter(Student.family_id == family_id).all()
    student_ids = [s.id for s in students]
    contracts = (
        db.query(Contract).filter(Contract.student_id.in_(student_ids)).all() if student_ids else []
    )
    invoices_query = db.query(FamilyInvoice).filter(FamilyInvoice.family_id == family_id)
    if user.role == UserRole.PARENT:
        invoices_query = invoices_query.filter(
            FamilyInvoice.status != FamilyInvoiceStatus.PENDING_REVIEW
        )
    invoices = invoices_query.all()

    invoice_rows = []
    for invoice in invoices:
        row = FamilyInvoiceRead.model_validate(invoice).model_dump(mode="json")
        if user.role == UserRole.PARENT:
            row["extracted_data"] = None
        invoice_rows.append(row)
    return {
        "family": FamilyRead.model_validate(family).model_dump(mode="json"),
        "students": [StudentRead.model_validate(s).model_dump(mode="json") for s in students],
        "contracts": [ContractRead.model_validate(c).model_dump(mode="json") for c in contracts],
        "family_invoices": invoice_rows,
    }


@router.post("/{family_id}/anonymize", status_code=status.HTTP_204_NO_CONTENT)
def anonymize_family(
    family_id: uuid.UUID,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> None:
    """TASK-0012 (derecho de supresión, RGPD) — mecanismo, no política.

    Anonimiza identificadores personales (nombre, dirección, fecha de
    nacimiento, colegio, email de login) pero conserva los registros de
    facturación: la normativa contable obliga a retenerlos aunque la familia
    ejerza su derecho de supresión sobre los datos personales. Irreversible;
    solo staff/admin, nunca autoservicio.
    """
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Familia no encontrada")

    before = {"name": family.name, "address": family.address, "status": family.status}
    family.name = f"Familia anonimizada {family.id}"
    family.address = None
    family.status = FamilyStatus.INACTIVE
    record_field_changes(
        db,
        entity_type=AuditedEntityType.FAMILY,
        entity_id=family.id,
        editor_id=staff.id,
        before=before,
        after={"name": family.name, "address": None, "status": family.status},
    )

    for student in db.query(Student).filter(Student.family_id == family_id).all():
        student_before = {
            "name": student.name,
            "birth_date": student.birth_date,
            "school": student.school,
        }
        student.name = f"Alumno anonimizado {student.id}"
        student.birth_date = None
        student.school = None
        student.status = StudentStatus.INACTIVE
        record_field_changes(
            db,
            entity_type=AuditedEntityType.STUDENT,
            entity_id=student.id,
            editor_id=staff.id,
            before=student_before,
            after={"name": student.name, "birth_date": None, "school": None},
        )

    for member in db.query(User).filter(User.family_id == family_id).all():
        member.email = f"anonimizado-{member.id}@example.invalid"
        member.name = "Usuario anonimizado"

    db.commit()

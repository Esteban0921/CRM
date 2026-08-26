import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from audit import record_field_changes
from db import get_db
from dependencies import ensure_family_access, get_current_user, require_role
from models.audit_log import AuditedEntityType
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.user import User, UserRole
from schemas.family_invoice import FamilyInvoiceRead, FamilyInvoiceUpdate

router = APIRouter(prefix="/family-invoices", tags=["family-invoices"])


def _with_family_names(db: Session, invoices: list[FamilyInvoice]) -> list[FamilyInvoiceRead]:
    """El tablero kanban (staff) necesita un nombre legible, no un UUID crudo.
    `FamilyInvoice` no tiene `relationship()` a `Family` (estilo del resto del
    proyecto): se resuelve con una sola query extra en vez de N+1.
    """
    family_ids = {invoice.family_id for invoice in invoices if invoice.family_id is not None}
    names = (
        dict(db.query(Family.id, Family.name).filter(Family.id.in_(family_ids)).all())
        if family_ids
        else {}
    )
    return [
        FamilyInvoiceRead.model_validate(invoice).model_copy(
            update={"family_name": names.get(invoice.family_id)}
        )
        for invoice in invoices
    ]


@router.get("", response_model=list[FamilyInvoiceRead])
def list_family_invoices(
    invoice_status: FamilyInvoiceStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FamilyInvoiceRead]:
    query = db.query(FamilyInvoice)
    if user.role == UserRole.PARENT:
        if user.family_id is None:
            return []
        query = query.filter(FamilyInvoice.family_id == user.family_id)
    if invoice_status is not None:
        query = query.filter(FamilyInvoice.status == invoice_status)
    # Cola de revision (TASK-0014): confianza mas baja primero.
    invoices = query.order_by(FamilyInvoice.confidence.asc().nullsfirst()).all()
    return _with_family_names(db, invoices)


@router.get("/{invoice_id}", response_model=FamilyInvoiceRead)
def get_family_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FamilyInvoiceRead:
    invoice = db.get(FamilyInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    ensure_family_access(user, invoice.family_id)
    return _with_family_names(db, [invoice])[0]


@router.patch("/{invoice_id}", response_model=FamilyInvoiceRead)
def update_family_invoice(
    invoice_id: uuid.UUID,
    payload: FamilyInvoiceUpdate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> FamilyInvoiceRead:
    invoice = db.get(FamilyInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(invoice, field) for field in changes}
    for field, value in changes.items():
        setattr(invoice, field, value)
    record_field_changes(
        db,
        entity_type=AuditedEntityType.FAMILY_INVOICE,
        entity_id=invoice.id,
        editor_id=staff.id,
        before=before,
        after=changes,
    )
    db.commit()
    db.refresh(invoice)
    return _with_family_names(db, [invoice])[0]

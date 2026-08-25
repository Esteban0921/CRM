import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from audit import record_field_changes
from db import get_db
from dependencies import ensure_family_access, get_current_user, require_role
from models.audit_log import AuditedEntityType
from models.contract import Contract
from models.family import Family, FamilyStatus
from models.family_invoice import FamilyInvoice
from models.student import Student, StudentStatus
from models.user import User, UserRole
from schemas.contract import ContractRead
from schemas.family import FamilyCreate, FamilyRead, FamilyUpdate
from schemas.family_invoice import FamilyInvoiceRead
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
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[Family]:
    return db.query(Family).order_by(Family.name).all()


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
    invoices = db.query(FamilyInvoice).filter(FamilyInvoice.family_id == family_id).all()

    return {
        "family": FamilyRead.model_validate(family).model_dump(mode="json"),
        "students": [StudentRead.model_validate(s).model_dump(mode="json") for s in students],
        "contracts": [ContractRead.model_validate(c).model_dump(mode="json") for c in contracts],
        "family_invoices": [
            FamilyInvoiceRead.model_validate(i).model_dump(mode="json") for i in invoices
        ],
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

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from audit import record_field_changes
from db import get_db
from dependencies import ensure_family_access, get_current_user, require_role
from models.audit_log import AuditedEntityType
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.user import User, UserRole
from schemas.family_invoice import FamilyInvoiceRead, FamilyInvoiceUpdate

router = APIRouter(prefix="/family-invoices", tags=["family-invoices"])


@router.get("", response_model=list[FamilyInvoiceRead])
def list_family_invoices(
    invoice_status: FamilyInvoiceStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FamilyInvoice]:
    query = db.query(FamilyInvoice)
    if user.role == UserRole.PARENT:
        if user.family_id is None:
            return []
        query = query.filter(FamilyInvoice.family_id == user.family_id)
    if invoice_status is not None:
        query = query.filter(FamilyInvoice.status == invoice_status)
    # Cola de revision (TASK-0014): confianza mas baja primero.
    return query.order_by(FamilyInvoice.confidence.asc().nullsfirst()).all()


@router.get("/{invoice_id}", response_model=FamilyInvoiceRead)
def get_family_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FamilyInvoice:
    invoice = db.get(FamilyInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    ensure_family_access(user, invoice.family_id)
    return invoice


@router.patch("/{invoice_id}", response_model=FamilyInvoiceRead)
def update_family_invoice(
    invoice_id: uuid.UUID,
    payload: FamilyInvoiceUpdate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> FamilyInvoice:
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
    return invoice

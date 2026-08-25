import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from audit import record_field_changes
from db import get_db
from dependencies import require_role
from models.audit_log import AuditedEntityType
from models.supplier_invoice import SupplierInvoice, SupplierInvoiceStatus
from models.user import User, UserRole
from schemas.supplier_invoice import SupplierInvoiceRead, SupplierInvoiceUpdate

# Solo staff/admin en todos los endpoints: un padre nunca ve gastos internos (RULE-005).
router = APIRouter(prefix="/supplier-invoices", tags=["supplier-invoices"])


@router.get("", response_model=list[SupplierInvoiceRead])
def list_supplier_invoices(
    invoice_status: SupplierInvoiceStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[SupplierInvoice]:
    query = db.query(SupplierInvoice)
    if invoice_status is not None:
        query = query.filter(SupplierInvoice.status == invoice_status)
    return query.order_by(SupplierInvoice.confidence.asc().nullsfirst()).all()


@router.get("/{invoice_id}", response_model=SupplierInvoiceRead)
def get_supplier_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> SupplierInvoice:
    invoice = db.get(SupplierInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    return invoice


@router.patch("/{invoice_id}", response_model=SupplierInvoiceRead)
def update_supplier_invoice(
    invoice_id: uuid.UUID,
    payload: SupplierInvoiceUpdate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> SupplierInvoice:
    invoice = db.get(SupplierInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(invoice, field) for field in changes}
    for field, value in changes.items():
        setattr(invoice, field, value)
    record_field_changes(
        db,
        entity_type=AuditedEntityType.SUPPLIER_INVOICE,
        entity_id=invoice.id,
        editor_id=staff.id,
        before=before,
        after=changes,
    )
    db.commit()
    db.refresh(invoice)
    return invoice

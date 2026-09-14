import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from models.supplier import SupplierCategory
from models.supplier_invoice import SupplierInvoiceStatus


class SupplierInvoiceUpdate(BaseModel):
    supplier_id: uuid.UUID | None = None
    category: SupplierCategory | None = None
    amount: Decimal | None = None
    issue_date: datetime.date | None = None
    due_date: datetime.date | None = None
    status: SupplierInvoiceStatus | None = None


class SupplierInvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    supplier_id: uuid.UUID | None
    supplier_name: str | None = None
    category: SupplierCategory
    amount: Decimal | None
    currency: str
    issue_date: datetime.date | None
    due_date: datetime.date | None
    status: SupplierInvoiceStatus
    extracted_data: dict | None
    confidence: float | None

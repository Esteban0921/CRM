import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from models.family_invoice import FamilyInvoiceStatus


class FamilyInvoiceUpdate(BaseModel):
    family_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    contract_id: uuid.UUID | None = None
    amount: Decimal | None = None
    issue_date: datetime.date | None = None
    due_date: datetime.date | None = None
    status: FamilyInvoiceStatus | None = None


class FamilyInvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    family_id: uuid.UUID | None
    family_name: str | None = None
    student_id: uuid.UUID | None
    contract_id: uuid.UUID | None
    amount: Decimal | None
    currency: str
    issue_date: datetime.date | None
    due_date: datetime.date | None
    status: FamilyInvoiceStatus
    extracted_data: dict | None
    confidence: float | None
    possible_duplicate: bool = False
    days_in_queue: int | None = None
    days_overdue: int | None = None

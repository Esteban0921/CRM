import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from models.family_invoice import FamilyInvoiceStatus
from models.notification_outbox import NotificationKind, NotificationStatus


class FamilyBilling(BaseModel):
    outstanding_amount: Decimal
    overdue_amount: Decimal
    overdue_count: int
    sent_count: int
    paid_count: int
    due_soon_count: int = 0
    due_soon_amount: Decimal = Decimal("0.00")
    currency: str = "EUR"


class StaffBillingSummary(BaseModel):
    pending_review_count: int
    overdue_count: int
    families_with_debt: int
    families_count: int
    overdue_amount: Decimal
    outstanding_amount: Decimal
    year_month: str
    expected_amount: Decimal = Decimal("0.00")
    collected_amount: Decimal = Decimal("0.00")
    due_soon_count: int = 0
    due_soon_amount: Decimal = Decimal("0.00")
    pending_tasks: int = 0
    failed_emails: int = 0
    unbilled_families: int = 0
    currency: str = "EUR"


class AtRiskFamily(BaseModel):
    id: uuid.UUID
    name: str
    overdue_amount: Decimal
    overdue_count: int
    pending_tasks: int


class DuplicateGroup(BaseModel):
    family_id: uuid.UUID
    family_name: str | None
    amount: Decimal
    issue_date: datetime.date
    invoice_ids: list[uuid.UUID]


class OverdueReminderResult(BaseModel):
    """Lo que se ha ENCOLADO, no lo que se ha enviado (TASK-0105).

    El campo `sent` desaparece a proposito: este endpoint no toca el SMTP, asi
    que no puede afirmar que algo haya salido. Antes devolvia `sent: 1,
    families: 37` con Mailpit apagado y sin que saliera un solo correo, y las
    36 familias sin usuario padre se saltaban en silencio.
    """

    queued: int
    already_queued: int
    families: int
    families_without_recipient: int
    pending_in_outbox: int


class FlushOutcome(BaseModel):
    """Resultado de vaciar la bandeja contra el SMTP real."""

    sent: int
    failed: int
    pending: int
    transport_available: bool
    errors: list[str] = []


class OutboxItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: NotificationKind
    recipient: str
    subject: str
    family_id: uuid.UUID | None
    invoice_id: uuid.UUID | None
    status: NotificationStatus
    attempts: int
    last_error: str | None
    created_at: datetime.datetime
    sent_at: datetime.datetime | None


class UnbilledFamily(BaseModel):
    id: uuid.UUID
    name: str
    expected_amount: Decimal
    currency: str = "EUR"


class InboxItem(BaseModel):
    kind: str
    title: str
    href: str
    count: int


class FamilyInvoiceBulkUpdate(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    status: FamilyInvoiceStatus | None = None
    family_id: uuid.UUID | None = None


class BulkItemError(BaseModel):
    id: uuid.UUID
    detail: str


class FamilyInvoiceBulkResult(BaseModel):
    updated: int
    failed: list[BulkItemError]


class FamilyMonthRow(BaseModel):
    id: uuid.UUID
    name: str
    expected_amount: Decimal
    collected_amount: Decimal
    outstanding_amount: Decimal
    overdue_amount: Decimal
    unbilled: bool
    currency: str = "EUR"


class MonthReport(BaseModel):
    year_month: str
    families: list[FamilyMonthRow]


class UnbilledTasksResult(BaseModel):
    created: int
    skipped: int
    year_month: str

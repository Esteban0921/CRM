from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from billing import (
    invoice_is_due_soon,
    invoice_is_overdue,
    promote_overdue_invoices,
    unbilled_by_family,
)
from db import get_db
from dependencies import get_current_user, require_role
from models.email import Email, EmailProcessingStatus
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.task import Task, TaskStatus
from models.user import User, UserRole
from notifications.email_sender import EmailSender, get_email_sender
from notifications.service import (
    PAYMENT_CLAIM_TITLE,
    notify_due_soon_invoices,
    notify_overdue_invoices,
)
from schemas.billing import InboxItem, OverdueReminderResult

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/overdue-reminders", response_model=OverdueReminderResult)
def send_overdue_reminders(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
    sender: EmailSender = Depends(get_email_sender),
) -> OverdueReminderResult:
    """Un correo por padre de cada familia con facturas vencidas. Nunca `pending_review`."""
    sent, families = notify_overdue_invoices(db, sender)
    return OverdueReminderResult(sent=sent, families=families)


@router.post("/due-soon-reminders", response_model=OverdueReminderResult)
def send_due_soon_reminders(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
    sender: EmailSender = Depends(get_email_sender),
) -> OverdueReminderResult:
    sent, families = notify_due_soon_invoices(db, sender)
    return OverdueReminderResult(sent=sent, families=families)


@router.get("/inbox", response_model=list[InboxItem])
def staff_inbox(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[InboxItem]:
    promote_overdue_invoices(db)
    invoices = db.query(FamilyInvoice).all()
    pending = sum(1 for invoice in invoices if invoice.status == FamilyInvoiceStatus.PENDING_REVIEW)
    overdue = sum(1 for invoice in invoices if invoice_is_overdue(invoice))
    due_soon = sum(1 for invoice in invoices if invoice_is_due_soon(invoice))
    failed = db.query(Email).filter(Email.processing_status == EmailProcessingStatus.FAILED).count()
    unbilled = len(unbilled_by_family(db))
    claims = (
        db.query(Task)
        .filter(Task.status == TaskStatus.PENDING, Task.title == PAYMENT_CLAIM_TITLE)
        .count()
    )
    items = [
        InboxItem(
            kind="pending_review",
            title="Facturas por revisar",
            href="/dashboard/invoices",
            count=pending,
        ),
        InboxItem(
            kind="overdue",
            title="Facturas vencidas",
            href="/dashboard/invoices",
            count=overdue,
        ),
        InboxItem(
            kind="due_soon",
            title="Vencen en 7 días",
            href="/dashboard/invoices",
            count=due_soon,
        ),
        InboxItem(
            kind="failed_emails",
            title="Correos fallidos",
            href="/dashboard/emails",
            count=failed,
        ),
        InboxItem(
            kind="unbilled",
            title="Familias sin facturar este mes",
            href="/dashboard",
            count=unbilled,
        ),
        InboxItem(
            kind="payment_claims",
            title="Padres que indican haber pagado",
            href="/dashboard/tasks",
            count=claims,
        ),
    ]
    return [item for item in items if item.count > 0]


@router.get("/mine", response_model=list[InboxItem])
def parent_inbox(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[InboxItem]:
    """TASK-0077. Solo el padre: vencidas y 7 días de su familia. RULE-017."""
    if user.role != UserRole.PARENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizado para este recurso")
    if user.family_id is None:
        return []
    promote_overdue_invoices(db)
    invoices = (
        db.query(FamilyInvoice)
        .filter(
            FamilyInvoice.family_id == user.family_id,
            FamilyInvoice.status != FamilyInvoiceStatus.PENDING_REVIEW,
        )
        .all()
    )
    overdue = sum(1 for invoice in invoices if invoice_is_overdue(invoice))
    due_soon = sum(1 for invoice in invoices if invoice_is_due_soon(invoice))
    items = [
        InboxItem(
            kind="overdue",
            title="Facturas vencidas",
            href="/dashboard",
            count=overdue,
        ),
        InboxItem(
            kind="due_soon",
            title="Vencen en 7 días",
            href="/dashboard",
            count=due_soon,
        ),
    ]
    return [item for item in items if item.count > 0]

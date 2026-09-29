from __future__ import annotations

from calendar import monthrange
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus


def invoice_is_overdue(invoice: FamilyInvoice, today: date | None = None) -> bool:
    """Vencida de verdad: estado `overdue`, o `sent` con `due_date` ya pasada."""
    today = today or date.today()
    if invoice.status in {FamilyInvoiceStatus.PAID, FamilyInvoiceStatus.PENDING_REVIEW}:
        return False
    if invoice.status == FamilyInvoiceStatus.OVERDUE:
        return True
    return (
        invoice.status == FamilyInvoiceStatus.SENT
        and invoice.due_date is not None
        and invoice.due_date < today
    )


def invoice_is_outstanding(invoice: FamilyInvoice, today: date | None = None) -> bool:
    if invoice.status in {FamilyInvoiceStatus.PAID, FamilyInvoiceStatus.PENDING_REVIEW}:
        return False
    if invoice.status in {FamilyInvoiceStatus.SENT, FamilyInvoiceStatus.OVERDUE}:
        return True
    return invoice_is_overdue(invoice, today)


def invoice_amount(invoice: FamilyInvoice) -> Decimal:
    """El importe nominal de la factura."""
    return invoice.amount if invoice.amount is not None else Decimal("0.00")


def invoice_outstanding(invoice: FamilyInvoice) -> Decimal:
    """Lo que queda por cobrar, ya descontados los pagos parciales (TASK-0157).

    Una familia que ha pagado 40 de 100 debe 60, no 100. Sin esto, registrar un
    pago parcial no cambiaria nada de lo que ve el staff y seria puro adorno.
    """
    cobrado = Decimal(str(getattr(invoice, "paid_amount", 0) or 0))
    resto = invoice_amount(invoice) - cobrado
    return resto if resto > Decimal("0.00") else Decimal("0.00")


def unbilled_task_title(today: date | None = None) -> str:
    today = today or date.today()
    return f"Facturar el mes {today.year:04d}-{today.month:02d}"


def month_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    start = today.replace(day=1)
    end = today.replace(day=monthrange(today.year, today.month)[1])
    return start, end


def _as_utc_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(UTC).date()
        return value.date()
    return value


def invoice_days_in_queue(invoice: FamilyInvoice, today: date | None = None) -> int | None:
    today = today or date.today()
    if invoice.status != FamilyInvoiceStatus.PENDING_REVIEW:
        return None
    created = _as_utc_date(invoice.created_at)
    if created is None:
        return None
    return max(0, (today - created).days)


def invoice_days_overdue(invoice: FamilyInvoice, today: date | None = None) -> int | None:
    today = today or date.today()
    if not invoice_is_overdue(invoice, today) or invoice.due_date is None:
        return None
    return max(0, (today - invoice.due_date).days)


def invoice_is_due_soon(invoice: FamilyInvoice, today: date | None = None, days: int = 7) -> bool:
    today = today or date.today()
    if invoice.status != FamilyInvoiceStatus.SENT or invoice.due_date is None:
        return False
    return today <= invoice.due_date <= today + timedelta(days=days)


def duplicate_key(invoice: FamilyInvoice) -> tuple | None:
    if invoice.family_id is None or invoice.amount is None or invoice.issue_date is None:
        return None
    return (invoice.family_id, invoice.amount, invoice.issue_date)


def duplicate_keys(invoices: list[FamilyInvoice]) -> set[tuple]:
    counted = Counter(key for invoice in invoices if (key := duplicate_key(invoice)))
    return {key for key, count in counted.items() if count > 1}


def expected_fees_by_family(db: Session, today: date | None = None) -> dict:
    from models.contract import Contract, ContractStatus
    from models.student import Student

    start, end = month_bounds(today)
    expected: dict = defaultdict(lambda: Decimal("0.00"))
    rows = (
        db.query(Contract, Student)
        .join(Student, Student.id == Contract.student_id)
        .filter(Contract.status == ContractStatus.ACTIVE, Contract.start_date <= end)
        .all()
    )
    for contract, student in rows:
        if contract.end_date is not None and contract.end_date < start:
            continue
        expected[student.family_id] += contract.monthly_fee
    return dict(expected)


def billed_family_ids(db: Session, today: date | None = None) -> set:
    start, end = month_bounds(today)
    return {
        invoice.family_id
        for invoice in db.query(FamilyInvoice)
        .filter(
            FamilyInvoice.family_id.isnot(None),
            FamilyInvoice.issue_date >= start,
            FamilyInvoice.issue_date <= end,
        )
        .all()
    }


def unbilled_by_family(db: Session, today: date | None = None) -> dict:
    """Familias con contrato activo este mes y ninguna factura emitida en el mes.

    Cuenta como facturada cualquier `FamilyInvoice` ya enlazada con `issue_date`
    en el mes (incluye `pending_review`: staff ya tiene el documento en cola).
    """
    expected = expected_fees_by_family(db, today)
    billed = billed_family_ids(db, today)
    return {family_id: amount for family_id, amount in expected.items() if family_id not in billed}


def promote_overdue_invoices(db: Session, today: date | None = None) -> int:
    """TASK-0058: `sent` + fecha vencida pasa a `overdue` de oficio."""
    today = today or date.today()
    invoices = (
        db.query(FamilyInvoice)
        .filter(
            FamilyInvoice.status == FamilyInvoiceStatus.SENT,
            FamilyInvoice.due_date.isnot(None),
            FamilyInvoice.due_date < today,
        )
        .all()
    )
    for invoice in invoices:
        invoice.status = FamilyInvoiceStatus.OVERDUE
    if invoices:
        db.commit()
    return len(invoices)

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from billing import invoice_amount, invoice_is_due_soon, invoice_is_overdue
from models.family import Family
from models.family_invoice import FamilyInvoice
from models.user import User, UserRole
from notifications.email_sender import EmailSender

PAYMENT_CLAIM_TITLE = "El padre indica que ha pagado"


def close_payment_claim_tasks(db: Session, invoice: FamilyInvoice) -> int:
    """TASK-0070. El cobro confirmado cierra el aviso del padre."""
    from models.task import Task, TaskStatus

    if invoice.family_id is None:
        return 0
    marker = f"invoice:{invoice.id}"
    tasks = (
        db.query(Task)
        .filter(
            Task.family_id == invoice.family_id,
            Task.status == TaskStatus.PENDING,
            Task.title == PAYMENT_CLAIM_TITLE,
            Task.description.like(f"{marker}%"),
        )
        .all()
    )
    for task in tasks:
        task.status = TaskStatus.DONE
    return len(tasks)


def compose_new_invoice_notification(invoice: FamilyInvoice, family_name: str) -> tuple[str, str]:
    subject = f"Nueva factura disponible para {family_name}"
    amount = (
        f"{invoice.amount} {invoice.currency}"
        if invoice.amount
        else "importe pendiente de confirmar"
    )
    body = (
        f"Hola,\n\n"
        f"Tenéis una nueva factura de transporte disponible para revisar en el panel de familias.\n"
        f"Importe: {amount}\n\n"
        f"Un saludo."
    )
    return subject, body


def notify_new_family_invoice(db: Session, sender: EmailSender, invoice: FamilyInvoice) -> None:
    """Avisa a los padres cuando una factura **ya publicada** está lista.

    TASK-0048 / RULE-017: no se llama desde la ingesta. El padre no debe
    enterarse de un dato que todavía no puede ver. No hace nada si la
    factura no está enlazada a una familia: no hay a quien avisar.
    """
    if invoice.family_id is None:
        return

    family = db.get(Family, invoice.family_id)
    parents = (
        db.query(User)
        .filter(User.family_id == invoice.family_id, User.role == UserRole.PARENT)
        .all()
    )
    if not parents:
        return

    subject, body = compose_new_invoice_notification(invoice, family.name if family else "")
    for parent in parents:
        sender.send(to=parent.email, subject=subject, body=body)


def compose_overdue_reminder(family_name: str, invoices: list[FamilyInvoice]) -> tuple[str, str]:
    total = sum((invoice_amount(invoice) for invoice in invoices), Decimal("0.00"))
    subject = f"Recordatorio de pago — {family_name}"
    lines = [
        "Hola,",
        "",
        f"Tenéis {len(invoices)} factura(s) de transporte vencida(s) o pendientes de pago.",
        f"Importe total: {total} EUR",
        "",
        "Entrad en el panel de familias para descargar la factura y regularizar el pago.",
        "",
        "Un saludo.",
    ]
    return subject, "\n".join(lines)


def notify_overdue_invoices(db: Session, sender: EmailSender) -> tuple[int, int]:
    """Avisa a los padres de familias con facturas vencidas (TASK-0053).

    Agrupa por familia: un correo por padre, no uno por factura.
    No incluye `pending_review` (RULE-017).
    """
    overdue = [
        invoice
        for invoice in db.query(FamilyInvoice).filter(FamilyInvoice.family_id.isnot(None)).all()
        if invoice_is_overdue(invoice)
    ]
    by_family: dict = defaultdict(list)
    for invoice in overdue:
        by_family[invoice.family_id].append(invoice)

    sent = 0
    for family_id, invoices in by_family.items():
        family = db.get(Family, family_id)
        parents = (
            db.query(User).filter(User.family_id == family_id, User.role == UserRole.PARENT).all()
        )
        if not parents:
            continue
        subject, body = compose_overdue_reminder(family.name if family else "", invoices)
        for parent in parents:
            sender.send(to=parent.email, subject=subject, body=body)
            sent += 1
    return sent, len(by_family)


def compose_due_soon_reminder(family_name: str, invoices: list[FamilyInvoice]) -> tuple[str, str]:
    total = sum((invoice_amount(invoice) for invoice in invoices), Decimal("0.00"))
    subject = f"Vencimiento próximo — {family_name}"
    lines = [
        "Hola,",
        "",
        f"Tenéis {len(invoices)} factura(s) de transporte que vencen en los próximos 7 días.",
        f"Importe: {total} EUR",
        "",
        "Entrad en el panel para descargar la factura y evitar recargos.",
        "",
        "Un saludo.",
    ]
    return subject, "\n".join(lines)


def notify_due_soon_invoices(db: Session, sender: EmailSender) -> tuple[int, int]:
    upcoming = [
        invoice
        for invoice in db.query(FamilyInvoice).filter(FamilyInvoice.family_id.isnot(None)).all()
        if invoice_is_due_soon(invoice)
    ]
    by_family: dict = defaultdict(list)
    for invoice in upcoming:
        by_family[invoice.family_id].append(invoice)
    sent = 0
    for family_id, invoices in by_family.items():
        family = db.get(Family, family_id)
        parents = (
            db.query(User).filter(User.family_id == family_id, User.role == UserRole.PARENT).all()
        )
        if not parents:
            continue
        subject, body = compose_due_soon_reminder(family.name if family else "", invoices)
        for parent in parents:
            sender.send(to=parent.email, subject=subject, body=body)
            sent += 1
    return sent, len(by_family)

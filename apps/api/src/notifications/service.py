from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from billing import invoice_amount, invoice_is_due_soon, invoice_is_overdue
from models.family import Family
from models.family_invoice import FamilyInvoice
from models.notification_outbox import NotificationKind
from models.user import User, UserRole
from notifications.outbox import enqueue

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


@dataclass
class ReminderOutcome:
    """Lo que de verdad paso, desglosado.

    Antes la respuesta era `sent: 1, families: 37`: las 36 familias sin usuario
    padre se saltaban en silencio y eso contaba como exito. Ahora se dicen por
    separado, porque "no tiene a quien avisar" es un problema de datos que
    alguien tiene que resolver, no un envio correcto (TASK-0105).
    """

    queued: int = 0
    already_queued: int = 0
    families: int = 0
    families_without_recipient: int = 0


def _queue_reminders(
    db: Session,
    by_family: dict,
    *,
    kind: NotificationKind,
    prefix: str,
    compose,
) -> ReminderOutcome:
    outcome = ReminderOutcome(families=len(by_family))
    # Una familia recibe como mucho un recordatorio de cada tipo al dia: el
    # doble clic en el boton mandaba dos correos identicos a 90 ms de
    # distancia (TASK-0104).
    today = date.today().isoformat()
    for family_id, invoices in by_family.items():
        family = db.get(Family, family_id)
        parents = (
            db.query(User).filter(User.family_id == family_id, User.role == UserRole.PARENT).all()
        )
        if not parents:
            outcome.families_without_recipient += 1
            continue
        subject, body = compose(family.name if family else "", invoices)
        for parent in parents:
            row = enqueue(
                db,
                kind=kind,
                dedupe_key=f"{prefix}:{family_id}:{parent.id}:{today}",
                recipient=parent.email,
                subject=subject,
                body=body,
                family_id=family_id,
            )
            if row is None:
                outcome.already_queued += 1
            else:
                outcome.queued += 1
    return outcome


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


def notify_new_family_invoice(db: Session, invoice: FamilyInvoice) -> int:
    """Avisa a los padres cuando una factura **ya publicada** está lista.

    TASK-0048 / RULE-017: no se llama desde la ingesta. El padre no debe
    enterarse de un dato que todavía no puede ver. No hace nada si la
    factura no está enlazada a una familia: no hay a quien avisar.
    """
    if invoice.family_id is None:
        return 0

    family = db.get(Family, invoice.family_id)
    parents = (
        db.query(User)
        .filter(User.family_id == invoice.family_id, User.role == UserRole.PARENT)
        .all()
    )
    if not parents:
        return 0

    subject, body = compose_new_invoice_notification(invoice, family.name if family else "")
    queued = 0
    for parent in parents:
        # Una factura se anuncia UNA vez. Antes, como el disparo era "el estado
        # anterior era pending_review y ahora no", rebotar el estado reenviaba
        # el correo: tres rebotes, tres correos al mismo padre (TASK-0104).
        row = enqueue(
            db,
            kind=NotificationKind.NEW_INVOICE,
            dedupe_key=f"new_invoice:{invoice.id}:{parent.id}",
            recipient=parent.email,
            subject=subject,
            body=body,
            family_id=invoice.family_id,
            invoice_id=invoice.id,
        )
        if row is not None:
            queued += 1
    return queued


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


def notify_overdue_invoices(db: Session) -> ReminderOutcome:
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
    return _queue_reminders(
        db,
        by_family,
        kind=NotificationKind.OVERDUE_REMINDER,
        prefix="overdue",
        compose=compose_overdue_reminder,
    )


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


def notify_due_soon_invoices(db: Session) -> ReminderOutcome:
    upcoming = [
        invoice
        for invoice in db.query(FamilyInvoice).filter(FamilyInvoice.family_id.isnot(None)).all()
        if invoice_is_due_soon(invoice)
    ]
    by_family: dict = defaultdict(list)
    for invoice in upcoming:
        by_family[invoice.family_id].append(invoice)
    return _queue_reminders(
        db,
        by_family,
        kind=NotificationKind.DUE_SOON_REMINDER,
        prefix="due_soon",
        compose=compose_due_soon_reminder,
    )

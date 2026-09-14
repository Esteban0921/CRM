from __future__ import annotations

from sqlalchemy.orm import Session

from models.family import Family
from models.family_invoice import FamilyInvoice
from models.user import User, UserRole
from notifications.email_sender import EmailSender


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

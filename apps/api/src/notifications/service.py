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
    """TASK-0015: el spec original era un dashboard "pull-only" — esto avisa
    quien tiene una factura nueva sin que tenga que entrar a comprobarlo.
    No hace nada si la factura todavia no esta enlazada a una familia
    (TASK-0030 no encontró match): no hay a quien avisar todavía.
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

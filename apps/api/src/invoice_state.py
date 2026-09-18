"""Maquina de estados de `FamilyInvoice` (TASK-0100, TASK-0101).

Antes no habia ninguna: la unica guardia del backend era «no salgas de
`pending_review` sin `family_id`», escrita dentro del PATCH. Todo lo demas se
aceptaba con 200, incluido `paid -> pending_review`, que deshace un cobro, lo
borra del mes y ademas esconde la factura al padre (RULE-017) — y tambien en
lote, con lo que se podian descobrar varias facturas de un clic.

Esta guardia es el unico sitio por el que pasan PATCH, `/bulk` y
`/confirm-payment`, asi que lo que no este declarado aqui no ocurre.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus

PENDING = FamilyInvoiceStatus.PENDING_REVIEW
SENT = FamilyInvoiceStatus.SENT
PAID = FamilyInvoiceStatus.PAID
OVERDUE = FamilyInvoiceStatus.OVERDUE

# El ciclo real del negocio: se revisa, se publica, se cobra. Vencer es una
# consecuencia del calendario, no una decision; volver a revision solo se puede
# desde lo que aun no se ha cobrado.
ALLOWED_TRANSITIONS: dict[FamilyInvoiceStatus, set[FamilyInvoiceStatus]] = {
    PENDING: {PENDING, SENT},
    SENT: {SENT, PAID, OVERDUE, PENDING},
    OVERDUE: {OVERDUE, PAID, SENT, PENDING},
    PAID: {PAID},
}

PUBLISHED_STATES = {SENT, PAID, OVERDUE}


class InvoiceStateError(ValueError):
    """Motivo legible para el staff; el router lo traduce a 409 o 422."""

    def __init__(self, message: str, *, conflict: bool) -> None:
        super().__init__(message)
        self.conflict = conflict


def ensure_transition_allowed(current: FamilyInvoiceStatus, target: FamilyInvoiceStatus) -> None:
    if target in ALLOWED_TRANSITIONS[current]:
        return
    if current == PAID:
        raise InvoiceStateError(
            "Una factura cobrada no se puede devolver a otro estado. "
            "Si el cobro fue un error, emite una nota de credito.",
            conflict=True,
        )
    raise InvoiceStateError(
        f"Transicion no permitida: de «{current.value}» a «{target.value}».",
        conflict=True,
    )


def ensure_publishable(
    invoice: FamilyInvoice,
    *,
    family_id: object,
    amount: Decimal | None,
    issue_date: datetime.date | None,
    due_date: datetime.date | None,
) -> None:
    """Una factura publicada es la que ve el padre: no puede salir sin importe
    ni sin fecha.

    La auditoria publico una con `amount=null, issue_date=null` y el padre
    recibio un correo diciendo «importe pendiente de confirmar», con un total de
    deuda que ademas no la sumaba.
    """
    _ = invoice
    if family_id is None:
        raise InvoiceStateError("Asigna una familia antes de publicar la factura", conflict=False)
    if amount is None:
        raise InvoiceStateError(
            "Indica el importe antes de publicar: el padre veria «importe pendiente»",
            conflict=False,
        )
    if amount <= 0:
        raise InvoiceStateError(
            "El importe de una factura publicada debe ser mayor que cero", conflict=False
        )
    if issue_date is None:
        raise InvoiceStateError(
            "Indica la fecha de emision antes de publicar: sin ella la factura no "
            "cuenta en el cierre del mes ni llega a vencer",
            conflict=False,
        )
    if due_date is not None and due_date < issue_date:
        raise InvoiceStateError(
            "El vencimiento no puede ser anterior a la fecha de emision", conflict=False
        )

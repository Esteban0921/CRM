"""Registro de cobros sobre facturas de familia (TASK-0157, TASK-0102).

`paid` era solo un valor de `status`: no habia fecha de cobro, ni importe
cobrado, ni metodo, ni forma de anotar un pago parcial. Eso obligaba a calcular
«cobrado este mes» filtrando por `issue_date`, con lo que una factura de agosto
pagada en septiembre no aparecia en el cierre de ningun mes.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.payment import Payment, PaymentMethod

ZERO = Decimal("0.00")


def paid_total(db: Session, invoice_id: uuid.UUID) -> Decimal:
    rows = db.query(Payment.amount).filter(Payment.invoice_id == invoice_id).all()
    return sum((row[0] for row in rows), ZERO)


def outstanding_for(db: Session, invoice: FamilyInvoice) -> Decimal:
    """Lo que queda por cobrar de una factura, ya descontados los pagos."""
    if invoice.amount is None:
        return ZERO
    resto = invoice.amount - paid_total(db, invoice.id)
    return resto if resto > ZERO else ZERO


def record_payment(
    db: Session,
    invoice: FamilyInvoice,
    *,
    amount: Decimal,
    paid_on: datetime.date,
    method: PaymentMethod = PaymentMethod.TRANSFER,
    reference: str | None = None,
    note: str | None = None,
    recorded_by: uuid.UUID | None = None,
) -> Payment:
    """Anota un cobro y salda la factura si ya esta cubierta.

    No hace `commit`: el llamador decide la transaccion, para que el pago y el
    cambio de estado entren juntos o no entren.
    """
    payment = Payment(
        invoice_id=invoice.id,
        amount=amount,
        currency=invoice.currency,
        paid_on=paid_on,
        method=method,
        reference=reference,
        note=note,
        recorded_by=recorded_by,
    )
    db.add(payment)
    db.flush()
    settle_if_covered(db, invoice)
    return payment


def settle_if_covered(db: Session, invoice: FamilyInvoice) -> bool:
    """Pasa la factura a `paid` cuando los pagos cubren el importe.

    Un pago parcial NO la salda: la factura sigue viva y su deuda es el resto,
    que es lo que hace util registrar el pago en vez de marcar «pagada» a ojo.
    """
    if invoice.amount is None:
        return False
    if paid_total(db, invoice.id) < invoice.amount:
        return False
    if invoice.status != FamilyInvoiceStatus.PAID:
        invoice.status = FamilyInvoiceStatus.PAID
    if invoice.paid_at is None:
        invoice.paid_at = _last_payment_date(db, invoice.id)
    return True


def _last_payment_date(db: Session, invoice_id: uuid.UUID) -> datetime.date | None:
    """La factura queda saldada el dia del ULTIMO pago que la cubre."""
    row = (
        db.query(Payment.paid_on)
        .filter(Payment.invoice_id == invoice_id)
        .order_by(Payment.paid_on.desc())
        .first()
    )
    return row[0] if row else None


def settle_without_payment_record(
    db: Session, invoice: FamilyInvoice, *, recorded_by: uuid.UUID | None
) -> Payment | None:
    """Marcar `paid` a mano sigue funcionando, pero deja rastro.

    El kanban y `/bulk` permiten mover una factura a `paid` de un tiron. Si eso
    no generase un cobro, el importe desapareceria del cierre del mes: la
    factura constaria pagada y la suma de pagos seria cero.
    """
    if invoice.amount is None:
        invoice.paid_at = invoice.paid_at or datetime.date.today()
        return None
    resto = outstanding_for(db, invoice)
    if resto <= ZERO:
        invoice.paid_at = invoice.paid_at or _last_payment_date(db, invoice.id)
        return None
    return record_payment(
        db,
        invoice,
        amount=resto,
        paid_on=datetime.date.today(),
        method=PaymentMethod.OTHER,
        note="Marcada como pagada sin detallar el cobro",
        recorded_by=recorded_by,
    )


def collected_between(db: Session, start: datetime.date, end: datetime.date) -> Decimal:
    """Cobrado en un periodo, por fecha de COBRO.

    Antes se sumaban las facturas `paid` cuya `issue_date` caia en el mes: un
    cobro de septiembre sobre una factura de agosto era invisible en septiembre
    y ademas cambiaba retroactivamente el cierre de agosto.
    """
    rows = db.query(Payment.amount).filter(Payment.paid_on >= start, Payment.paid_on <= end).all()
    return sum((row[0] for row in rows), ZERO)


def collected_between_by_family(
    db: Session, start: datetime.date, end: datetime.date
) -> dict[uuid.UUID, Decimal]:
    rows = (
        db.query(FamilyInvoice.family_id, Payment.amount)
        .join(FamilyInvoice, FamilyInvoice.id == Payment.invoice_id)
        .filter(Payment.paid_on >= start, Payment.paid_on <= end)
        .all()
    )
    totales: dict[uuid.UUID, Decimal] = {}
    for family_id, amount in rows:
        if family_id is None:
            continue
        totales[family_id] = totales.get(family_id, ZERO) + amount
    return totales

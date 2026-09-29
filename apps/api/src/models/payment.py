from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.mixins import IdMixin, utcnow


class PaymentMethod(enum.StrEnum):
    TRANSFER = "transfer"
    DIRECT_DEBIT = "direct_debit"
    CASH = "cash"
    CARD = "card"
    OTHER = "other"


class Payment(IdMixin, Base):
    """Un cobro real sobre una factura (TASK-0157).

    Hasta ahora `paid` era solo un valor de `status`: no habia fecha de cobro,
    ni importe cobrado, ni metodo, ni forma de registrar un pago parcial. La
    consecuencia contable la midio la auditoria: `collected_amount` se calculaba
    filtrando por `issue_date`, asi que una factura de agosto pagada en
    septiembre no aparecia en el cierre de ningun mes.

    `paid_on` es la fecha en que entro el dinero, que es la unica que sirve para
    cerrar un mes. `created_at` es cuando alguien lo apunto, que puede ser otro
    dia y no vale para contabilidad.
    """

    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family_invoices.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    paid_on: Mapped[datetime.date] = mapped_column(Date, index=True)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(
            PaymentMethod,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=PaymentMethod.TRANSFER,
    )
    reference: Mapped[str | None] = mapped_column(String(120), default=None)
    note: Mapped[str | None] = mapped_column(String(255), default=None)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(default=utcnow)

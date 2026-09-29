from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal

from sqlalchemy import JSON, Date, Enum, ForeignKey, Numeric, String, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column

from db import Base
from models.mixins import IdMixin, TimestampMixin
from models.payment import Payment


class FamilyInvoiceStatus(enum.StrEnum):
    PENDING_REVIEW = "pending_review"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"


class FamilyInvoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "family_invoices"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    # Nullable: la ingesta automatica no sabe todavia a que familia pertenece
    # un documento; queda sin enlazar (status=pending_review) hasta que staff
    # lo asigna manualmente (o una futura tarea de matching automatico).
    family_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("families.id"), default=None)
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("students.id"), default=None)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), default=None)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    issue_date: Mapped[datetime.date | None] = mapped_column(Date, default=None)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, default=None)
    status: Mapped[FamilyInvoiceStatus] = mapped_column(
        Enum(
            FamilyInvoiceStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=FamilyInvoiceStatus.PENDING_REVIEW,
    )
    # Fecha en que la factura quedo saldada, no la de emision (TASK-0102).
    # `collected_amount` se calculaba filtrando por `issue_date`: una factura
    # de agosto pagada en septiembre no aparecia en el cierre de ningun mes.
    paid_at: Mapped[datetime.date | None] = mapped_column(Date, default=None, index=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    confidence: Mapped[float | None] = mapped_column(default=None)


# Suma de los cobros de esta factura, como subconsulta correlacionada: sin esto
# un pago parcial no reduciria la deuda y registrarlo seria puro adorno. Va en
# el SELECT, asi que no hay N+1; y desde TASK-0126 los listados estan paginados,
# con lo que el coste esta acotado.
FamilyInvoice.paid_amount = column_property(
    select(func.coalesce(func.sum(Payment.amount), 0))
    .where(Payment.invoice_id == FamilyInvoice.id)
    .correlate_except(Payment)
    .scalar_subquery(),
    deferred=False,
)

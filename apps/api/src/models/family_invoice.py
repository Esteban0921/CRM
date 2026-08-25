from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal

from sqlalchemy import JSON, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.mixins import IdMixin, TimestampMixin


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
    extracted_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    confidence: Mapped[float | None] = mapped_column(default=None)

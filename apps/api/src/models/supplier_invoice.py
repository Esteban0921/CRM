from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal

from sqlalchemy import JSON, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.mixins import IdMixin, TimestampMixin
from models.supplier import SupplierCategory


class SupplierInvoiceStatus(enum.StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PAID = "paid"


class SupplierInvoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "supplier_invoices"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"), default=None)
    category: Mapped[SupplierCategory] = mapped_column(
        Enum(
            SupplierCategory,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=SupplierCategory.OTHER,
    )
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    issue_date: Mapped[datetime.date | None] = mapped_column(Date, default=None)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, default=None)
    status: Mapped[SupplierInvoiceStatus] = mapped_column(
        Enum(
            SupplierInvoiceStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=SupplierInvoiceStatus.PENDING_REVIEW,
    )
    extracted_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    confidence: Mapped[float | None] = mapped_column(default=None)

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.mixins import IdMixin, utcnow


class AuditedEntityType(enum.StrEnum):
    FAMILY = "family"
    STUDENT = "student"
    CONTRACT = "contract"
    FAMILY_INVOICE = "family_invoice"
    SUPPLIER_INVOICE = "supplier_invoice"


class AuditLog(IdMixin, Base):
    """Trazabilidad de correcciones manuales (RULE-009 / auditoria 2026-08-25,
    TASK-0014). entity_id no es FK: apunta a family_invoices o supplier_invoices
    segun entity_type, tablas distintas.
    """

    __tablename__ = "audit_logs"

    entity_type: Mapped[AuditedEntityType] = mapped_column(
        Enum(
            AuditedEntityType,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    entity_id: Mapped[uuid.UUID] = mapped_column()
    field_name: Mapped[str] = mapped_column(String(100))
    old_value: Mapped[str | None] = mapped_column(Text, default=None)
    new_value: Mapped[str | None] = mapped_column(Text, default=None)
    edited_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from models.mixins import IdMixin, utcnow

if TYPE_CHECKING:
    from models.email import Email


class DocumentType(enum.StrEnum):
    FAMILY_INVOICE = "family_invoice"
    SUPPLIER_INVOICE = "supplier_invoice"
    CREDIT_NOTE = "credit_note"
    OTHER = "other"
    UNKNOWN = "unknown"


class Document(IdMixin, Base):
    """Un fichero descargado de un Email. Inmutable: sin updated_at (RULE-016:
    el fichero original no se reprocesa in-place, se genera un Document nuevo).
    """

    __tablename__ = "documents"

    email_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("emails.id"))
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(
            DocumentType,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=DocumentType.UNKNOWN,
    )
    file_path: Mapped[str] = mapped_column(String(1000))
    original_filename: Mapped[str | None] = mapped_column(String(500), default=None)
    mime_type: Mapped[str | None] = mapped_column(String(200), default=None)
    file_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    is_zip_member: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_zip_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    email: Mapped[Email] = relationship(back_populates="documents")

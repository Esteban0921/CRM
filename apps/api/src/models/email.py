from __future__ import annotations

import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from models.document import Document


class EmailProcessingStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"


class Email(IdMixin, TimestampMixin, Base):
    __tablename__ = "emails"

    gmail_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(100), default=None)
    subject: Mapped[str | None] = mapped_column(String(500), default=None)
    from_address: Mapped[str | None] = mapped_column(String(255), default=None)
    received_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    raw_headers: Mapped[dict | None] = mapped_column(JSON, default=None)
    body_plain: Mapped[str | None] = mapped_column(Text, default=None)
    body_html: Mapped[str | None] = mapped_column(Text, default=None)
    labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    processing_status: Mapped[EmailProcessingStatus] = mapped_column(
        Enum(
            EmailProcessingStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=EmailProcessingStatus.PENDING,
    )
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    documents: Mapped[list[Document]] = relationship(back_populates="email")

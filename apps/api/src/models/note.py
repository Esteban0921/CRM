from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.mixins import IdMixin, utcnow


class NoteEntityType(enum.StrEnum):
    FAMILY = "family"
    STUDENT = "student"


class Note(IdMixin, Base):
    """Nota interna de staff (TASK-0025, hallazgo de auditoría comparativa:
    Krayin/NextCRM/Atomic CRM tienen notas libres por contacto). Nunca
    visible para `parent` — es información de trabajo del equipo, no un
    canal de comunicación con la familia.
    """

    __tablename__ = "notes"

    entity_type: Mapped[NoteEntityType] = mapped_column(
        Enum(
            NoteEntityType,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    entity_id: Mapped[uuid.UUID] = mapped_column()
    body: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

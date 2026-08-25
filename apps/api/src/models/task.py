from __future__ import annotations

import datetime
import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from models.family import Family


class TaskStatus(enum.StrEnum):
    PENDING = "pending"
    DONE = "done"
    CANCELLED = "cancelled"


class Task(IdMixin, TimestampMixin, Base):
    """Recordatorio/seguimiento de staff vinculado a una familia (TASK-0027,
    hallazgo de auditoría comparativa: patrón común en CRMs — ej. "contactar
    por impago"). No lo ve nunca un `parent`.
    """

    __tablename__ = "tasks"

    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("families.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, default=None)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
        ),
        default=TaskStatus.PENDING,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    family: Mapped[Family] = relationship()

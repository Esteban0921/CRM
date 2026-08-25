from __future__ import annotations

import datetime
import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from models.contract import Contract
    from models.family import Family


class StudentStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Student(IdMixin, TimestampMixin, Base):
    __tablename__ = "students"

    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("families.id"))
    name: Mapped[str] = mapped_column(String(200))
    birth_date: Mapped[datetime.date | None] = mapped_column(Date, default=None)
    school: Mapped[str | None] = mapped_column(String(200), default=None)
    status: Mapped[StudentStatus] = mapped_column(
        Enum(
            StudentStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=StudentStatus.ACTIVE,
    )

    family: Mapped[Family] = relationship(back_populates="students")
    contracts: Mapped[list[Contract]] = relationship(back_populates="student")

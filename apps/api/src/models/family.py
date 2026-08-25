from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from models.student import Student
    from models.user import User


class FamilyStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Family(IdMixin, TimestampMixin, Base):
    __tablename__ = "families"

    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    status: Mapped[FamilyStatus] = mapped_column(
        Enum(
            FamilyStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=FamilyStatus.ACTIVE,
    )

    students: Mapped[list[Student]] = relationship(back_populates="family")
    users: Mapped[list[User]] = relationship(back_populates="family")

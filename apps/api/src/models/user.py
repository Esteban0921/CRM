from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from models.family import Family


class UserRole(enum.StrEnum):
    PARENT = "parent"
    STAFF = "staff"
    ADMIN = "admin"


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])
    )
    # Solo se rellena cuando role = parent (RULE-005 de AGENTS.md).
    family_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("families.id"), default=None)

    family: Mapped[Family | None] = relationship(back_populates="users")

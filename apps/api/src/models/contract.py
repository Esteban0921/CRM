from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from models.student import Student


class ContractStatus(enum.StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class Contract(IdMixin, TimestampMixin, Base):
    __tablename__ = "contracts"

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"))
    service_type: Mapped[str] = mapped_column(String(100))
    monthly_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    start_date: Mapped[datetime.date] = mapped_column(Date)
    end_date: Mapped[datetime.date | None] = mapped_column(Date, default=None)
    status: Mapped[ContractStatus] = mapped_column(
        Enum(
            ContractStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ContractStatus.ACTIVE,
    )

    student: Mapped[Student] = relationship(back_populates="contracts")

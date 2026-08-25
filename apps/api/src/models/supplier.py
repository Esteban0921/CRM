import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.mixins import IdMixin, TimestampMixin


class SupplierCategory(enum.StrEnum):
    FUEL = "fuel"
    MAINTENANCE = "maintenance"
    INSURANCE = "insurance"
    OTHER = "other"


class Supplier(IdMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(200))
    tax_id: Mapped[str | None] = mapped_column(String(50), default=None)
    # Usado por ingestion.classification para distinguir factura de
    # proveedor vs. factura a familia cuando llegan al mismo buzon.
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    category: Mapped[SupplierCategory] = mapped_column(
        Enum(
            SupplierCategory,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=SupplierCategory.OTHER,
    )

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from models.family import FamilyStatus


class FamilyCreate(BaseModel):
    name: str
    address: str | None = None


class FamilyUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    status: FamilyStatus | None = None


class FamilyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None
    status: FamilyStatus
    outstanding_amount: Decimal = Decimal("0.00")
    overdue_amount: Decimal = Decimal("0.00")
    unbilled: bool = False
    currency: str = "EUR"

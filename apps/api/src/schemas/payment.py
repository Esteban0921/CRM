import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from models.payment import PaymentMethod


class PaymentCreate(BaseModel):
    """Un cobro que alguien apunta (TASK-0157).

    `paid_on` es la fecha en que entro el dinero, no la de hoy: se registra a
    posteriori mas veces de las que se registra en el momento, y es la unica
    fecha que sirve para cerrar un mes.
    """

    amount: Decimal = Field(gt=0)
    paid_on: datetime.date | None = None
    method: PaymentMethod = PaymentMethod.TRANSFER
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=255)


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    currency: str
    paid_on: datetime.date
    method: PaymentMethod
    reference: str | None
    note: str | None
    created_at: datetime.datetime

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from models.contract import ContractStatus


class ContractCreate(BaseModel):
    student_id: uuid.UUID
    service_type: str
    monthly_fee: Decimal
    start_date: datetime.date
    end_date: datetime.date | None = None


class ContractUpdate(BaseModel):
    service_type: str | None = None
    monthly_fee: Decimal | None = None
    end_date: datetime.date | None = None
    status: ContractStatus | None = None


class ContractRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    service_type: str
    monthly_fee: Decimal
    start_date: datetime.date
    end_date: datetime.date | None
    status: ContractStatus

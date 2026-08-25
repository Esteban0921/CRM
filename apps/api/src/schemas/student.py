import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from models.student import StudentStatus


class StudentCreate(BaseModel):
    family_id: uuid.UUID
    name: str
    birth_date: datetime.date | None = None
    school: str | None = None


class StudentUpdate(BaseModel):
    name: str | None = None
    birth_date: datetime.date | None = None
    school: str | None = None
    status: StudentStatus | None = None


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    birth_date: datetime.date | None
    school: str | None
    status: StudentStatus

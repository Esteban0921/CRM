import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from models.task import TaskStatus


class TaskCreate(BaseModel):
    family_id: uuid.UUID
    title: str
    description: str | None = None
    due_date: datetime.date | None = None
    assigned_to: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime.date | None = None
    status: TaskStatus | None = None
    assigned_to: uuid.UUID | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    title: str
    description: str | None
    due_date: datetime.date | None
    status: TaskStatus
    assigned_to: uuid.UUID | None
    created_by: uuid.UUID
    family_name: str | None = None

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.note import NoteEntityType


class NoteCreate(BaseModel):
    entity_type: NoteEntityType
    entity_id: uuid.UUID
    body: str


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: NoteEntityType
    entity_id: uuid.UUID
    body: str
    created_by: uuid.UUID
    created_at: datetime

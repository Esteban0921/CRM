import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SearchHit(BaseModel):
    type: Literal["family", "student", "family_invoice", "supplier"]
    id: uuid.UUID
    title: str
    subtitle: str | None = None
    family_id: uuid.UUID | None = None


class SearchResponse(BaseModel):
    hits: list[SearchHit]


class ActivityEvent(BaseModel):
    at: datetime
    kind: Literal["audit", "note"]
    title: str
    detail: str | None = None
    actor_name: str | None = None

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from models.document import DocumentType


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_type: DocumentType
    original_filename: str | None
    mime_type: str | None
    created_at: datetime.datetime

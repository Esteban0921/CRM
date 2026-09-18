import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from models.email import EmailProcessingStatus


class EmailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    gmail_id: str
    subject: str | None
    from_address: str | None
    processing_status: EmailProcessingStatus
    error_message: str | None
    created_at: datetime.datetime
    document_count: int = 0

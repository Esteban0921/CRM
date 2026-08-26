import datetime

from pydantic import BaseModel, Field


class RawAttachmentIn(BaseModel):
    filename: str
    mime_type: str = "application/octet-stream"
    content_base64: str


class RawEmailIn(BaseModel):
    gmail_id: str
    thread_id: str | None = None
    subject: str | None = None
    from_address: str | None = None
    received_at: datetime.datetime | None = None
    body_plain: str | None = None
    body_html: str | None = None
    attachments: list[RawAttachmentIn] = Field(default_factory=list)


class IngestionRunRequest(BaseModel):
    """Gmail real sigue pendiente (TASK-0032): mientras tanto, quien llama a
    /ingestion/run aporta los correos "recibidos" (simulados) aquí mismo.
    """

    emails: list[RawEmailIn] = Field(default_factory=list)


class IngestionRunResult(BaseModel):
    processed: int
    skipped_already_processed: int
    failed: list[str]

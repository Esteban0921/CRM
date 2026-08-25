from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RawAttachment:
    filename: str
    mime_type: str
    content: bytes


@dataclass
class RawEmail:
    gmail_id: str
    thread_id: str | None = None
    subject: str | None = None
    from_address: str | None = None
    received_at: datetime.datetime | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body_plain: str | None = None
    body_html: str | None = None
    labels: list[str] = field(default_factory=list)
    attachments: list[RawAttachment] = field(default_factory=list)


class GmailClient(Protocol):
    """Puerto hacia Gmail. `FakeGmailClient` lo implementa con credenciales
    simuladas (decisión 2026-08-25 del usuario); un cliente real con OAuth
    (google-api-python-client) implementaría el mismo protocolo sin tocar
    el orquestador de `pipeline.py`.
    """

    def list_new_message_ids(self) -> list[str]: ...

    def get_message(self, message_id: str) -> RawEmail: ...

    def apply_label(self, message_id: str, label: str) -> None: ...

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from config import settings


class EmailSender(Protocol):
    def send(self, *, to: str, subject: str, body: str) -> None: ...


@dataclass
class SentEmail:
    to: str
    subject: str
    body: str


@dataclass
class NoOpEmailSender:
    """No envia nada de verdad — dev/tests. Guarda lo "enviado" en `sent`
    para poder verificarlo desde un test sin un servidor SMTP real.
    """

    sent: list[SentEmail] = field(default_factory=list)

    def send(self, *, to: str, subject: str, body: str) -> None:
        self.sent.append(SentEmail(to=to, subject=subject, body=body))


class SmtpEmailSender:
    """Real: smtplib contra SMTP_HOST/SMTP_PORT (Mailpit en desarrollo).
    Verificado en TASK-0034 end-to-end contra Mailpit real.
    """

    def send(self, *, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.smtp_from
        message["To"] = to
        message.set_content(body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as client:
            client.send_message(message)

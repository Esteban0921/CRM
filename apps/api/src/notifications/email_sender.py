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


def get_email_sender() -> EmailSender | None:
    """El transporte real, o `None` si no hay ninguno (TASK-0105).

    Antes caia a `NoOpEmailSender` en silencio: con Mailpit apagado la API
    respondia «enviado» y no salia un solo correo. Un doble de pruebas no puede
    ser el plan B de produccion — `NoOpEmailSender` se construye a mano en los
    tests, y aqui devolver `None` obliga al llamador a decir la verdad.

    El sondeo TCP solo ocurre en el flush. Cuando estaba en `Depends` de cada
    endpoint costaba 3 s en CADA `PATCH`, publicara o no.
    """
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=3.0):
            pass
    except OSError:
        return None
    return SmtpEmailSender()


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

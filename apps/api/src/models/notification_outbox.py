from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.mixins import IdMixin, utcnow


class NotificationKind(enum.StrEnum):
    NEW_INVOICE = "new_invoice"
    OVERDUE_REMINDER = "overdue_reminder"
    DUE_SOON_REMINDER = "due_soon_reminder"


class NotificationStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationOutbox(IdMixin, Base):
    """Bandeja de salida de los avisos a las familias (TASK-0104).

    Antes el envio ocurria dentro del request que publicaba la factura, con un
    `except OSError: pass` alrededor. Consecuencias medidas en la auditoria:

    - Con el SMTP caido la factura quedaba publicada, el padre no se enteraba,
      no habia registro de que el aviso no salio y no habia forma de
      reintentarlo.
    - `Depends(get_email_sender)` hacia un sondeo TCP en CADA peticion: +3 s en
      PATCH que ni siquiera publicaban nada.
    - Rebotar el estado reenviaba el correo: tres rebotes, tres correos al
      mismo padre.
    - Y ante una familia que dice «a mi no me avisasteis» no habia respuesta.

    La fila se inserta en la MISMA transaccion que publica la factura, asi que
    o se publica y queda encolado el aviso, o no ocurre ninguna de las dos
    cosas. `dedupe_key` es unico: la deduplicacion la impone la base de datos,
    no un check-then-insert que se pierde en cuanto hay dos peticiones a la vez.
    """

    __tablename__ = "notification_outbox"

    kind: Mapped[NotificationKind] = mapped_column(
        Enum(
            NotificationKind,
            native_enum=False,
            length=30,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    recipient: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    family_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("families.id"), default=None, index=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(
            NotificationStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=NotificationStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

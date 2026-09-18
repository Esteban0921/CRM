"""Encolar y vaciar la bandeja de salida de avisos (TASK-0104, TASK-0105).

El envio sale del camino de la peticion. Publicar una factura **encola**; un
paso aparte intenta el SMTP de verdad y anota lo que paso. Eso arregla, de una
vez, cuatro cosas que la auditoria midio:

- El aviso ya no se pierde en silencio (`except OSError: pass`).
- El aviso ya no se duplica al rebotar el estado de la factura.
- La respuesta deja de mentir: `{"sent": 1}` con el SMTP apagado.
- Y desaparece el sondeo TCP de 3 s que penalizaba CADA `PATCH`, publicara o no.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.notification_outbox import (
    NotificationKind,
    NotificationOutbox,
    NotificationStatus,
)
from notifications.email_sender import EmailSender

MAX_ATTEMPTS = 5


@dataclass
class FlushResult:
    sent: int = 0
    failed: int = 0
    pending: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def enqueue(
    db: Session,
    *,
    kind: NotificationKind,
    dedupe_key: str,
    recipient: str,
    subject: str,
    body: str,
    family_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
) -> NotificationOutbox | None:
    """Encola un aviso. Devuelve `None` si ya estaba encolado.

    La unicidad la impone el indice de `dedupe_key`, no una consulta previa: un
    check-then-insert se pierde en cuanto hay dos peticiones a la vez, y eso es
    exactamente lo que pasaba con el doble clic en «Recordatorios de
    vencimiento» (dos correos identicos a 90 ms de distancia).
    """
    existing = (
        db.query(NotificationOutbox).filter(NotificationOutbox.dedupe_key == dedupe_key).first()
    )
    if existing is not None:
        return None

    row = NotificationOutbox(
        kind=kind,
        dedupe_key=dedupe_key,
        recipient=recipient,
        subject=subject,
        body=body,
        family_id=family_id,
        invoice_id=invoice_id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        # Otra peticion gano la carrera: no es un error, es la deduplicacion
        # funcionando.
        db.rollback()
        return None
    return row


def pending_count(db: Session) -> int:
    return (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.status == NotificationStatus.PENDING)
        .count()
    )


def flush(db: Session, sender: EmailSender | None, limit: int = 100) -> FlushResult:
    """Intenta enviar lo encolado y anota el resultado fila a fila.

    `sender=None` significa que no hay transporte disponible: no se marca nada
    como enviado y se dice por que. Antes se caia a `NoOpEmailSender` en
    silencio y el staff veia «enviado» sin que saliera un solo correo.
    """
    result = FlushResult()
    rows = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.status == NotificationStatus.PENDING,
            NotificationOutbox.attempts < MAX_ATTEMPTS,
        )
        .order_by(NotificationOutbox.created_at)
        .limit(limit)
        .all()
    )

    if sender is None:
        result.pending = len(rows)
        if rows:
            result.errors.append("No hay transporte SMTP disponible: nada se ha enviado.")
        return result

    for row in rows:
        row.attempts += 1
        try:
            sender.send(to=row.recipient, subject=row.subject, body=row.body)
        except Exception as exc:  # noqa: BLE001 - un destinatario roto no para la bandeja
            row.last_error = str(exc)[:500]
            if row.attempts >= MAX_ATTEMPTS:
                row.status = NotificationStatus.FAILED
            result.failed += 1
            result.errors.append(f"{row.recipient}: {exc}")
            continue
        row.status = NotificationStatus.SENT
        row.sent_at = datetime.datetime.now(datetime.UTC)
        row.last_error = None
        result.sent += 1

    db.commit()
    result.pending = pending_count(db)
    return result

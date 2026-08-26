import base64
import smtplib

import clamd
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import settings
from db import get_db
from dependencies import require_role
from ingestion.fake_gmail_client import FakeGmailClient
from ingestion.gmail_client import RawAttachment, RawEmail
from ingestion.pipeline import ingest_new_emails
from ingestion.scanning import AttachmentScanner, ClamdScanner
from models.user import User, UserRole
from notifications.email_sender import EmailSender, NoOpEmailSender, SmtpEmailSender
from schemas.ingestion import IngestionRunRequest, IngestionRunResult

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def _build_scanner() -> AttachmentScanner:
    """RULE-016: los adjuntos no confiables deben pasar por el antivirus real
    (TASK-0033) antes de tratarse como una factura. Si el daemon no responde,
    falla cerrado en vez de degradar en silencio a "sin escanear": un
    servicio auxiliar caido no debe convertirse en una forma de saltarse un
    control de seguridad nombrado explícitamente en AGENTS.md.
    """
    try:
        client = clamd.ClamdNetworkSocket(
            host=settings.clamav_host, port=settings.clamav_port, timeout=3.0
        )
        client.ping()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Antivirus (clamd) no disponible: no se puede escanear con seguridad "
            "los adjuntos entrantes (RULE-016). Comprueba el servicio `clamav` "
            "de docker-compose.yml.",
        ) from exc
    return ClamdScanner(host=settings.clamav_host, port=settings.clamav_port)


def _build_sender() -> EmailSender:
    """A diferencia del antivirus, un aviso por email que no sale no es un
    problema de seguridad (ver docstring de `ingest_new_emails`): si Mailpit
    no responde, la ingesta sigue sin avisar a nadie en vez de fallar entera.
    """
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=3.0):
            pass
        return SmtpEmailSender()
    except OSError:
        return NoOpEmailSender()


@router.post("/run", response_model=IngestionRunResult)
def run_ingestion(
    payload: IngestionRunRequest,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> IngestionRunResult:
    """TASK-0041: punto de entrada real a `ingestion/pipeline.py`, que hasta
    ahora ningun router invocaba (solo se ejercitaba desde tests). Gmail real
    sigue pospuesto a proposito (TASK-0032): quien llama aporta los correos
    "recibidos" (simulados) en el propio payload.
    """
    try:
        inbox = [
            RawEmail(
                gmail_id=item.gmail_id,
                thread_id=item.thread_id,
                subject=item.subject,
                from_address=item.from_address,
                received_at=item.received_at,
                body_plain=item.body_plain,
                body_html=item.body_html,
                attachments=[
                    RawAttachment(
                        filename=attachment.filename,
                        mime_type=attachment.mime_type,
                        content=base64.b64decode(attachment.content_base64, validate=True),
                    )
                    for attachment in item.attachments
                ],
            )
            for item in payload.emails
        ]
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Adjunto con base64 invalido: {exc}"
        ) from exc
    summary = ingest_new_emails(
        FakeGmailClient(inbox=inbox),
        db,
        storage_dir=settings.attachments_dir,
        scanner=_build_scanner(),
        sender=_build_sender(),
    )
    return IngestionRunResult(
        processed=summary.processed,
        skipped_already_processed=summary.skipped_already_processed,
        failed=summary.failed,
    )

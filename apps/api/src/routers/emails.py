import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import settings
from db import get_db
from dependencies import require_role
from ingestion.fake_gmail_client import FakeGmailClient
from ingestion.gmail_client import RawAttachment, RawEmail
from ingestion.pipeline import ingest_new_emails
from ingestion.scanning import ScannerUnavailableError, build_attachment_scanner
from models.document import Document
from models.email import Email, EmailProcessingStatus
from models.user import User, UserRole
from schemas.email import EmailRead, ReprocessResult

router = APIRouter(prefix="/emails", tags=["emails"])


def _scanner():
    try:
        return build_attachment_scanner()
    except ScannerUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("", response_model=list[EmailRead])
def list_emails(
    processing_status: EmailProcessingStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[EmailRead]:
    query = db.query(Email)
    if processing_status is not None:
        query = query.filter(Email.processing_status == processing_status)
    emails = query.order_by(Email.created_at.desc()).limit(100).all()
    doc_counts = dict(
        db.query(Document.email_id, func.count(Document.id)).group_by(Document.email_id).all()
    )
    return [
        EmailRead.model_validate(email).model_copy(
            update={"document_count": int(doc_counts.get(email.id, 0))}
        )
        for email in emails
    ]


@router.post("/{email_id}/reprocess", response_model=ReprocessResult)
def reprocess_email(
    email_id: uuid.UUID,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> ReprocessResult:
    """Reintenta un correo que fallo (TASK-0118).

    Hasta ahora no habia ninguna accion posible sobre un correo `failed`: la
    guardia de idempotencia era «existe este gmail_id?», asi que el propio
    fallo bloqueaba el reintento y la factura no llegaba nunca a la cola. El
    contador «Correos fallidos» del panel subia y no se podia hacer nada con el.

    El adjunto original ya esta en disco, pero el pipeline reconstruye el correo
    desde los campos guardados: asi el reproceso pasa otra vez por el antivirus
    (RULE-016) en vez de dar por buena una copia local.
    """
    email = db.get(Email, email_id)
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Correo no encontrado")
    if email.processing_status == EmailProcessingStatus.PROCESSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este correo ya se proceso correctamente")

    documents = db.query(Document).filter(Document.email_id == email.id).all()
    attachments: list[RawAttachment] = []
    missing: list[str] = []
    for document in documents:
        path = Path(document.file_path)
        if not path.is_file():
            missing.append(document.original_filename or str(document.id))
            continue
        attachments.append(
            RawAttachment(
                filename=document.original_filename or path.name,
                mime_type=document.mime_type or "application/octet-stream",
                content=path.read_bytes(),
            )
        )

    raw = RawEmail(
        gmail_id=email.gmail_id,
        thread_id=email.thread_id,
        subject=email.subject,
        from_address=email.from_address,
        received_at=email.received_at,
        body_plain=email.body_plain,
        body_html=email.body_html,
        attachments=attachments,
    )
    summary = ingest_new_emails(
        FakeGmailClient(inbox=[raw]),
        db,
        storage_dir=settings.attachments_dir,
        scanner=_scanner(),
    )
    db.refresh(email)
    return ReprocessResult(
        gmail_id=email.gmail_id,
        processing_status=email.processing_status,
        error_message=email.error_message,
        reprocessed=summary.processed == 1,
        missing_attachments=missing,
    )

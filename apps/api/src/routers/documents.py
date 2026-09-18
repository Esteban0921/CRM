import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import settings
from db import get_db
from dependencies import ensure_family_access, get_current_user, require_role
from models.document import Document, DocumentType
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.user import User, UserRole
from schemas.document import DocumentRead

router = APIRouter(prefix="/documents", tags=["documents"])


def _storage_root() -> Path:
    configured = Path(settings.attachments_dir)
    if configured.is_absolute():
        return configured
    api_root = Path(__file__).resolve().parents[2]
    return (api_root / configured).resolve()


def _existing_file(document: Document) -> Path:
    stored = Path(document.file_path)
    storage = _storage_root().resolve()
    candidates: list[Path] = []
    if stored.is_absolute():
        candidates.append(stored)
    else:
        candidates.append(storage / stored)
        candidates.append(storage / stored.name)
    if document.original_filename:
        candidates.append(storage / Path(document.original_filename).name)
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not resolved.is_file():
            continue
        if not stored.is_absolute() and not resolved.is_relative_to(storage):
            continue
        return resolved
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichero no disponible")


@router.get("", response_model=list[DocumentRead])
def list_documents(
    document_type: DocumentType | None = Query(default=None),
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[Document]:
    query = db.query(Document)
    if document_type is not None:
        query = query.filter(Document.document_type == document_type)
    return query.order_by(Document.created_at.desc()).all()


@router.get("/{document_id}/file")
def download_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    """TASK-0051. El padre solo baja el PDF de una factura suya ya publicada.

    RULE-015: no se loguea el contenido. RULE-017: `pending_review` → 404.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")

    invoice = db.query(FamilyInvoice).filter(FamilyInvoice.document_id == document.id).first()
    if user.role == UserRole.PARENT:
        if invoice is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
        ensure_family_access(user, invoice.family_id)
        if invoice.status == FamilyInvoiceStatus.PENDING_REVIEW:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")

    path = _existing_file(document)
    filename = document.original_filename or path.name
    media_type = document.mime_type or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=filename)

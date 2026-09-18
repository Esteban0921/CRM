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
    """Sirve exclusivamente el fichero que dice la fila, y solo si esta dentro
    de `ATTACHMENTS_DIR`.

    Antes habia dos fallbacks por nombre base -uno de ellos sobre
    `original_filename`, que lo controla integramente quien manda el correo-.
    Si el fichero propio desaparecia (cuarentena del antivirus, limpieza), la
    API devolvia los bytes de otro documento con el mismo nombre: autorizacion
    correcta, contenido de otra familia. Ademas la contencion solo se evaluaba
    para rutas relativas, y el pipeline guarda siempre rutas absolutas, con lo
    que no se aplicaba nunca (TASK-0091, RULE-005).
    """
    storage = _storage_root().resolve()
    stored = Path(document.file_path)
    candidate = stored if stored.is_absolute() else storage / stored
    try:
        resolved = candidate.resolve()
    except OSError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichero no disponible") from None
    if not resolved.is_relative_to(storage) or not resolved.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichero no disponible")
    return resolved


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

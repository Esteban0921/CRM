from __future__ import annotations

import hashlib
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from ingestion.classification import classify_document
from ingestion.extraction import extract_fields, parse_spanish_amount, parse_spanish_date
from ingestion.gmail_client import GmailClient, RawAttachment
from ingestion.matching import match_student_by_name_in_text
from ingestion.safe_zip import UnsafeArchiveError, safe_extract_zip
from ingestion.scanning import AttachmentScanner, NoOpScanner
from models.document import Document, DocumentType
from models.email import Email, EmailProcessingStatus
from models.family_invoice import FamilyInvoice
from models.supplier import Supplier
from models.supplier_invoice import SupplierInvoice
from notifications.email_sender import EmailSender


@dataclass
class IngestionSummary:
    processed: int = 0
    skipped_already_processed: int = 0
    failed: list[str] = field(default_factory=list)


def ingest_new_emails(
    client: GmailClient,
    db: Session,
    storage_dir: str | Path,
    scanner: AttachmentScanner | None = None,
    sender: EmailSender | None = None,
) -> IngestionSummary:
    """Orquesta la ingesta (spec original sección 6). `client` puede ser
    `FakeGmailClient` (credenciales simuladas) o, más adelante, uno real: el
    contrato es el mismo, este orquestador no cambia.

    `sender` se ignora a propósito (TASK-0048 / RULE-017): el aviso a la
    familia sale cuando staff publica la factura, no cuando el adjunto llega.
    """
    _ = sender
    scanner = scanner or NoOpScanner()
    storage = Path(storage_dir)
    storage.mkdir(parents=True, exist_ok=True)
    summary = IngestionSummary()
    known_supplier_addresses = {
        email.lower() for (email,) in db.query(Supplier.email).filter(Supplier.email.isnot(None))
    }

    for message_id in client.list_new_message_ids():
        # Idempotencia por EXITO, no por existencia (TASK-0118).
        #
        # Antes la guardia era "existe una fila con este gmail_id?". Un fallo
        # transitorio -ClamAV arrancando, Postgres cayendo a mitad- dejaba el
        # correo en `failed` y con eso bloqueaba su propio reintento para
        # siempre: la factura no llegaba a la cola de nadie y no habia forma de
        # recuperarla. `SPEC_ORIGINAL.md:178` prometia reintento.
        existing = db.query(Email).filter(Email.gmail_id == message_id).first()
        if existing is not None and existing.processing_status == EmailProcessingStatus.PROCESSED:
            summary.skipped_already_processed += 1
            continue

        try:
            raw = client.get_message(message_id)
        except Exception as exc:  # noqa: BLE001 - un mensaje ilegible no aborta el lote
            _mark_failed(db, message_id, str(exc))
            client.apply_label(message_id, "AUTO/FAILED")
            summary.failed.append(message_id)
            continue

        if existing is None:
            email = Email(gmail_id=raw.gmail_id)
            db.add(email)
        else:
            # Reintento: se reaprovecha la fila y se limpia lo que dejo el
            # intento anterior, para no acumular documentos a medias.
            email = existing
            email.error_message = None
            _discard_previous_attempt(db, email)

        email.thread_id = raw.thread_id
        email.subject = raw.subject
        email.from_address = raw.from_address
        email.received_at = raw.received_at
        email.raw_headers = raw.headers or None
        email.body_plain = raw.body_plain
        email.body_html = raw.body_html
        email.labels = list(raw.labels)
        email.processing_status = EmailProcessingStatus.PROCESSING

        try:
            # El flush entra en el try: antes quedaba fuera, asi que el
            # IntegrityError del unique de gmail_id escapaba sin capturar,
            # devolvia un 500 y abortaba el resto del lote (TASK-0119).
            db.flush()
            for attachment in raw.attachments:
                _process_attachment(
                    db=db,
                    email=email,
                    attachment=attachment,
                    storage=storage,
                    scanner=scanner,
                    known_supplier_addresses=known_supplier_addresses,
                )
            email.processing_status = EmailProcessingStatus.PROCESSED
            client.apply_label(message_id, "AUTO/PROCESSED")
            summary.processed += 1
            db.commit()
        except UnsafeArchiveError as exc:
            email.processing_status = EmailProcessingStatus.FAILED
            email.error_message = str(exc)
            client.apply_label(message_id, "AUTO/FAILED")
            summary.failed.append(message_id)
            db.commit()
        except Exception as exc:  # noqa: BLE001 - un correo roto no aborta el lote
            _mark_failed(db, message_id, str(exc))
            client.apply_label(message_id, "AUTO/FAILED")
            summary.failed.append(message_id)

    return summary


def _mark_failed(db: Session, message_id: str, error: str) -> None:
    """Deja el correo en `failed` con su motivo, sin perder la fila."""
    db.rollback()
    failed = db.query(Email).filter(Email.gmail_id == message_id).first()
    if failed is None:
        failed = Email(
            gmail_id=message_id,
            processing_status=EmailProcessingStatus.FAILED,
            error_message=error,
        )
        db.add(failed)
    else:
        failed.processing_status = EmailProcessingStatus.FAILED
        failed.error_message = error
    db.commit()


def _discard_previous_attempt(db: Session, email: Email) -> None:
    """Borra los documentos y facturas que dejo un intento fallido anterior.

    Sin esto, reprocesar un correo que fallo a mitad duplicaria las facturas que
    si se habian creado antes del fallo.
    """
    documents = db.query(Document).filter(Document.email_id == email.id).all()
    if not documents:
        return
    document_ids = [document.id for document in documents]
    db.query(FamilyInvoice).filter(FamilyInvoice.document_id.in_(document_ids)).delete(
        synchronize_session=False
    )
    db.query(SupplierInvoice).filter(SupplierInvoice.document_id.in_(document_ids)).delete(
        synchronize_session=False
    )
    db.query(Document).filter(Document.id.in_(document_ids)).delete(synchronize_session=False)
    db.flush()


def attachment_storage_path(storage: Path, filename: str, unique_id: uuid.UUID) -> Path:
    """Nunca escribe fuera de `storage`. El nombre del adjunto viene del correo
    (RULE-016): solo se usa el basename, prefijado con un UUID para no pisar.
    """
    root = storage.resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = Path(filename.replace("\\", "/")).name
    if not name or name in {".", ".."}:
        name = "attachment.bin"
    dest = (root / f"{unique_id}_{name}").resolve()
    if not dest.is_relative_to(root):
        dest = (root / f"{unique_id}_attachment.bin").resolve()
    return dest


def _process_attachment(
    *,
    db: Session,
    email: Email,
    attachment: RawAttachment,
    storage: Path,
    scanner: AttachmentScanner,
    known_supplier_addresses: set[str],
) -> None:
    if attachment.filename.lower().endswith(".zip"):
        _process_zip_attachment(
            db=db,
            email=email,
            attachment=attachment,
            storage=storage,
            scanner=scanner,
            known_supplier_addresses=known_supplier_addresses,
        )
        return

    _store_and_classify(
        db=db,
        email=email,
        filename=attachment.filename,
        content=attachment.content,
        mime_type=attachment.mime_type,
        storage=storage,
        scanner=scanner,
        is_zip_member=False,
        parent_zip_id=None,
        known_supplier_addresses=known_supplier_addresses,
    )


def _process_zip_attachment(
    *,
    db: Session,
    email: Email,
    attachment: RawAttachment,
    storage: Path,
    scanner: AttachmentScanner,
    known_supplier_addresses: set[str],
) -> None:
    dest_path = attachment_storage_path(storage, attachment.filename, uuid.uuid4())
    dest_path.write_bytes(attachment.content)
    scan_result = scanner.scan(dest_path)

    zip_doc = Document(
        email_id=email.id,
        document_type=DocumentType.OTHER if not scan_result.clean else DocumentType.UNKNOWN,
        file_path=str(dest_path),
        original_filename=Path(attachment.filename.replace("\\", "/")).name,
        mime_type=attachment.mime_type,
        file_hash=_hash_bytes(attachment.content),
        is_zip_member=False,
    )
    db.add(zip_doc)
    db.flush()

    if not scan_result.clean:
        return

    with tempfile.TemporaryDirectory() as tmp:
        extracted_paths = safe_extract_zip(dest_path, Path(tmp) / "extracted")
        for member_path in extracted_paths:
            _store_and_classify(
                db=db,
                email=email,
                filename=member_path.name,
                content=member_path.read_bytes(),
                mime_type="application/octet-stream",
                storage=storage,
                scanner=scanner,
                is_zip_member=True,
                parent_zip_id=zip_doc.id,
                known_supplier_addresses=known_supplier_addresses,
            )


def _store_and_classify(
    *,
    db: Session,
    email: Email,
    filename: str,
    content: bytes,
    mime_type: str,
    storage: Path,
    scanner: AttachmentScanner,
    is_zip_member: bool,
    parent_zip_id: uuid.UUID | None,
    known_supplier_addresses: set[str],
) -> None:
    dest_path = attachment_storage_path(storage, filename, uuid.uuid4())
    dest_path.write_bytes(content)

    scan_result = scanner.scan(dest_path)
    doc_type = classify_document(
        filename=filename,
        subject=email.subject,
        from_address=email.from_address,
        known_supplier_addresses=known_supplier_addresses,
    )
    if not scan_result.clean:
        # Se guarda como evidencia (nunca se borra un adjunto), pero no se
        # procesa como factura.
        doc_type = DocumentType.OTHER

    document = Document(
        email_id=email.id,
        document_type=doc_type,
        file_path=str(dest_path),
        original_filename=Path(filename.replace("\\", "/")).name or filename,
        mime_type=mime_type,
        file_hash=_hash_bytes(content),
        is_zip_member=is_zip_member,
        parent_zip_id=parent_zip_id,
    )
    db.add(document)
    db.flush()

    if scan_result.clean and doc_type in (
        DocumentType.FAMILY_INVOICE,
        DocumentType.SUPPLIER_INVOICE,
    ):
        # El "texto" se simula como el contenido decodificado (RawAttachment
        # de pruebas/FakeGmailClient); la extracción real de texto de PDF
        # (pypdf/pdfplumber, spec original) se conecta con muestras reales.
        text = content.decode("utf-8", errors="ignore")
        fields = extract_fields(text)
        _create_invoice_record(db, document, doc_type, fields, text)


def _create_invoice_record(
    db: Session,
    document: Document,
    doc_type: DocumentType,
    fields,
    text: str,
) -> None:
    extracted_data = {
        "invoice_number": fields.invoice_number,
        "issue_date": fields.issue_date,
        "total_amount": fields.total_amount,
        "tax_id": fields.tax_id,
    }
    amount = parse_spanish_amount(fields.total_amount)
    issue_date = parse_spanish_date(fields.issue_date)
    if doc_type == DocumentType.FAMILY_INVOICE:
        # TASK-0030: intenta enlazar automaticamente por nombre de alumno.
        # Aunque haya match, status sigue pending_review — el auto-match
        # ahorra trabajo a staff, no sustituye la revision humana (RULE-015).
        # TASK-0048 / RULE-017: no se notifica aqui; el padre no debe saber
        # de una factura que todavia no puede ver.
        family_id, student_id = match_student_by_name_in_text(db, text)
        invoice = FamilyInvoice(
            document_id=document.id,
            family_id=family_id,
            student_id=student_id,
            amount=amount,
            issue_date=issue_date,
            extracted_data=extracted_data,
            confidence=fields.confidence,
        )
        db.add(invoice)
        db.flush()
    else:
        db.add(
            SupplierInvoice(
                document_id=document.id,
                amount=amount,
                issue_date=issue_date,
                extracted_data=extracted_data,
                confidence=fields.confidence,
            )
        )


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

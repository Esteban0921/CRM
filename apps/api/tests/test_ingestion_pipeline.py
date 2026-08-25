import io
import zipfile

from ingestion.fake_gmail_client import FakeGmailClient
from ingestion.gmail_client import RawAttachment, RawEmail
from ingestion.pipeline import ingest_new_emails
from models.document import Document, DocumentType
from models.email import Email, EmailProcessingStatus
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.student import Student
from models.supplier import Supplier
from models.supplier_invoice import SupplierInvoice

FACTURA_TEXTO = """
FACTURA
Factura Nº: INV-2026-001
Fecha: 01/09/2026
NIF: B12345678
Total: 45,00 EUR
""".encode()


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_ingests_pdf_as_family_invoice_pending_review(db_session, tmp_path):
    client = FakeGmailClient(
        [
            RawEmail(
                gmail_id="msg-1",
                subject="Tu factura de transporte",
                from_address="admin@crm-transporte.local",
                attachments=[
                    RawAttachment(
                        filename="factura.pdf", mime_type="application/pdf", content=FACTURA_TEXTO
                    )
                ],
            )
        ]
    )

    summary = ingest_new_emails(client, db_session, storage_dir=tmp_path)

    assert summary.processed == 1
    email = db_session.query(Email).filter(Email.gmail_id == "msg-1").one()
    assert email.processing_status == EmailProcessingStatus.PROCESSED
    assert client.labels_for("msg-1") == ["AUTO/PROCESSED"]

    document = db_session.query(Document).filter(Document.email_id == email.id).one()
    assert document.document_type == DocumentType.FAMILY_INVOICE

    invoice = db_session.query(FamilyInvoice).filter(FamilyInvoice.document_id == document.id).one()
    assert invoice.family_id is None
    assert invoice.status.value == "pending_review"
    assert invoice.extracted_data["invoice_number"] == "INV-2026-001"
    assert invoice.confidence > 0


def test_ingests_zip_with_two_members(db_session, tmp_path):
    zip_content = _zip_bytes({"factura.pdf": FACTURA_TEXTO, "factura.xml": b"<Factura/>"})
    client = FakeGmailClient(
        [
            RawEmail(
                gmail_id="msg-2",
                subject="Factura adjunta",
                attachments=[
                    RawAttachment(
                        filename="paquete.zip", mime_type="application/zip", content=zip_content
                    )
                ],
            )
        ]
    )

    ingest_new_emails(client, db_session, storage_dir=tmp_path)

    email = db_session.query(Email).filter(Email.gmail_id == "msg-2").one()
    documents = db_session.query(Document).filter(Document.email_id == email.id).all()
    assert len(documents) == 3  # el zip + 2 miembros

    zip_doc = next(d for d in documents if not d.is_zip_member)
    members = [d for d in documents if d.is_zip_member]
    assert len(members) == 2
    assert all(m.parent_zip_id == zip_doc.id for m in members)


def test_processed_message_is_not_returned_as_new_by_the_client(db_session, tmp_path):
    client = FakeGmailClient([RawEmail(gmail_id="msg-3", attachments=[])])

    ingest_new_emails(client, db_session, storage_dir=tmp_path)

    assert client.list_new_message_ids() == []


def test_gmail_id_already_in_db_is_skipped_without_duplicating(db_session, tmp_path):
    # Defensa en profundidad: aunque Gmail devolviera otra vez un gmail_id ya
    # procesado (carrera, relabel manual...), nunca se procesa dos veces.
    db_session.add(Email(gmail_id="msg-3", processing_status=EmailProcessingStatus.PROCESSED))
    db_session.commit()
    client = FakeGmailClient([RawEmail(gmail_id="msg-3", attachments=[])])

    summary = ingest_new_emails(client, db_session, storage_dir=tmp_path)

    assert summary.processed == 0
    assert summary.skipped_already_processed == 1
    assert db_session.query(Email).filter(Email.gmail_id == "msg-3").count() == 1


def test_known_supplier_address_creates_supplier_invoice(db_session, tmp_path):
    db_session.add(Supplier(name="Repsol", email="facturas@repsol.com"))
    db_session.commit()
    client = FakeGmailClient(
        [
            RawEmail(
                gmail_id="msg-4",
                from_address="facturas@repsol.com",
                attachments=[
                    RawAttachment(
                        filename="factura.pdf", mime_type="application/pdf", content=FACTURA_TEXTO
                    )
                ],
            )
        ]
    )

    ingest_new_emails(client, db_session, storage_dir=tmp_path)

    email = db_session.query(Email).filter(Email.gmail_id == "msg-4").one()
    document = db_session.query(Document).filter(Document.email_id == email.id).one()
    assert document.document_type == DocumentType.SUPPLIER_INVOICE
    assert (
        db_session.query(SupplierInvoice).filter(SupplierInvoice.document_id == document.id).count()
        == 1
    )
    assert db_session.query(FamilyInvoice).count() == 0


def test_matching_student_name_auto_links_but_still_needs_review(db_session, tmp_path):
    family = Family(name="Familia Garcia")
    db_session.add(family)
    db_session.commit()
    db_session.add(Student(family_id=family.id, name="Ana Garcia Perez"))
    db_session.commit()
    texto_con_alumno = FACTURA_TEXTO.decode() + "\nAlumno: Ana Garcia Perez\n"
    client = FakeGmailClient(
        [
            RawEmail(
                gmail_id="msg-6",
                attachments=[
                    RawAttachment(
                        filename="factura.pdf",
                        mime_type="application/pdf",
                        content=texto_con_alumno.encode(),
                    )
                ],
            )
        ]
    )

    ingest_new_emails(client, db_session, storage_dir=tmp_path)

    invoice = db_session.query(FamilyInvoice).one()
    assert invoice.family_id == family.id
    assert invoice.status == FamilyInvoiceStatus.PENDING_REVIEW  # match no salta la revision


def test_zip_bomb_marks_email_as_failed_not_processed(db_session, tmp_path):
    huge_zip = _zip_bytes({"sospechoso.bin": b"A" * 5_000_000})
    client = FakeGmailClient(
        [
            RawEmail(
                gmail_id="msg-5",
                attachments=[
                    RawAttachment(
                        filename="paquete.zip", mime_type="application/zip", content=huge_zip
                    )
                ],
            )
        ]
    )

    summary = ingest_new_emails(client, db_session, storage_dir=tmp_path)

    assert summary.failed == ["msg-5"]
    email = db_session.query(Email).filter(Email.gmail_id == "msg-5").one()
    assert email.processing_status == EmailProcessingStatus.FAILED
    assert email.error_message is not None
    assert client.labels_for("msg-5") == ["AUTO/FAILED"]

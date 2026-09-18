"""Regresion de la perdida de datos silenciosa (TASK-0118, TASK-0119, TASK-0120).

La idempotencia era «existe este gmail_id?», no «se proceso bien?»: un fallo
transitorio dejaba el correo en `failed` y con eso bloqueaba su propio
reintento para siempre. La auditoria encontro 104 correos muertos en la base de
datos de desarrollo, con su adjunto en disco y sin ninguna factura detras.
"""

import uuid
from unittest.mock import MagicMock, patch

from ingestion.fake_gmail_client import FakeGmailClient
from ingestion.gmail_client import RawAttachment, RawEmail
from ingestion.pipeline import ingest_new_emails
from ingestion.scanning import NoOpScanner, ScannerUnavailableError
from models.document import Document
from models.email import Email, EmailProcessingStatus
from models.family_invoice import FamilyInvoice
from models.user import User, UserRole
from security import create_access_token, hash_password

FACTURA = b"FACTURA F-2026-77\nFecha: 05/09/2026\nNIF: B12345678\nTotal: 121,00 EUR\n"


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _staff(db_session) -> User:
    staff = User(
        email=f"staff-{uuid.uuid4()}@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    return staff


def _raw(gmail_id: str) -> RawEmail:
    return RawEmail(
        gmail_id=gmail_id,
        thread_id="t-1",
        subject="Factura de transporte",
        from_address="facturacion@colegio-demo.es",
        received_at=None,
        body_plain="Adjuntamos la factura.",
        body_html=None,
        attachments=[
            RawAttachment(filename="factura.pdf", mime_type="application/pdf", content=FACTURA)
        ],
    )


class _ExplodingScanner:
    """Reproduce ClamAV arrancando: vivo, y sin veredicto."""

    def __init__(self) -> None:
        self.calls = 0

    def scan(self, file_path):
        self.calls += 1
        raise ScannerUnavailableError("clamd cargando firmas")


def test_un_fallo_transitorio_ya_no_bloquea_el_reintento(db_session, attachments_dir):
    roto = _ExplodingScanner()

    primero = ingest_new_emails(
        FakeGmailClient(inbox=[_raw("g-1")]),
        db_session,
        storage_dir=str(attachments_dir),
        scanner=roto,
    )
    assert primero.processed == 0
    assert primero.failed == ["g-1"]

    # Segundo intento con el antivirus ya listo: antes devolvia
    # `skipped_already_processed: 1` y la factura no llegaba nunca.
    segundo = ingest_new_emails(
        FakeGmailClient(inbox=[_raw("g-1")]),
        db_session,
        storage_dir=str(attachments_dir),
        scanner=NoOpScanner(),
    )

    assert segundo.processed == 1, "el correo fallido seguia bloqueando su reintento"
    assert segundo.skipped_already_processed == 0
    email = db_session.query(Email).filter(Email.gmail_id == "g-1").one()
    assert email.processing_status == EmailProcessingStatus.PROCESSED
    assert email.error_message is None
    assert db_session.query(FamilyInvoice).count() == 1


def test_un_correo_ya_procesado_no_se_procesa_dos_veces(db_session, attachments_dir):
    for _ in range(2):
        summary = ingest_new_emails(
            FakeGmailClient(inbox=[_raw("g-2")]),
            db_session,
            storage_dir=str(attachments_dir),
            scanner=NoOpScanner(),
        )
    assert summary.skipped_already_processed == 1
    assert db_session.query(FamilyInvoice).count() == 1


def test_el_reintento_no_duplica_lo_que_creo_el_intento_anterior(db_session, attachments_dir):
    ingest_new_emails(
        FakeGmailClient(inbox=[_raw("g-3")]),
        db_session,
        storage_dir=str(attachments_dir),
        scanner=NoOpScanner(),
    )
    email = db_session.query(Email).filter(Email.gmail_id == "g-3").one()
    email.processing_status = EmailProcessingStatus.FAILED
    db_session.commit()

    ingest_new_emails(
        FakeGmailClient(inbox=[_raw("g-3")]),
        db_session,
        storage_dir=str(attachments_dir),
        scanner=NoOpScanner(),
    )

    assert db_session.query(Document).count() == 1
    assert db_session.query(FamilyInvoice).count() == 1


def test_un_correo_roto_no_aborta_el_resto_del_lote(db_session, attachments_dir):
    """El `db.flush()` quedaba fuera del try: el IntegrityError escapaba, el
    llamador recibia un 500 y los correos que faltaban no se veian nunca.
    """
    bueno_1 = _raw("g-ok-1")
    malo = RawEmail(
        gmail_id="g-malo",
        thread_id=None,
        subject=None,
        from_address=None,
        received_at=None,
        body_plain=None,
        body_html=None,
        attachments=[
            RawAttachment(filename="x.zip", mime_type="application/zip", content=b"no-es-un-zip")
        ],
    )
    bueno_2 = _raw("g-ok-2")

    summary = ingest_new_emails(
        FakeGmailClient(inbox=[bueno_1, malo, bueno_2]),
        db_session,
        storage_dir=str(attachments_dir),
        scanner=NoOpScanner(),
    )

    assert summary.processed == 2, "el correo roto se llevo por delante el resto del lote"
    assert "g-malo" in summary.failed


def test_staff_reprocesa_un_correo_fallido_desde_la_api(client, db_session, attachments_dir):
    ingest_new_emails(
        FakeGmailClient(inbox=[_raw("g-api")]),
        db_session,
        storage_dir=str(attachments_dir),
        scanner=NoOpScanner(),
    )
    email = db_session.query(Email).filter(Email.gmail_id == "g-api").one()
    email.processing_status = EmailProcessingStatus.FAILED
    email.error_message = "clamd cargando firmas"
    db_session.commit()

    scanner = MagicMock()
    scanner.instream.return_value = {"stream": ("OK", None)}
    scanner.version.return_value = "ClamAV 1.0.0"
    staff = _staff(db_session)
    with patch("clamd.ClamdNetworkSocket", return_value=scanner):
        response = client.post(f"/emails/{email.id}/reprocess", headers=_auth(staff))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reprocessed"] is True
    assert body["processing_status"] == "processed"
    assert body["error_message"] is None


def test_no_se_reprocesa_un_correo_que_fue_bien(client, db_session, attachments_dir):
    ingest_new_emails(
        FakeGmailClient(inbox=[_raw("g-ok")]),
        db_session,
        storage_dir=str(attachments_dir),
        scanner=NoOpScanner(),
    )
    email = db_session.query(Email).filter(Email.gmail_id == "g-ok").one()
    staff = _staff(db_session)

    response = client.post(f"/emails/{email.id}/reprocess", headers=_auth(staff))

    assert response.status_code == 409


def test_el_padre_no_reprocesa_correos(client, db_session, attachments_dir):
    ingest_new_emails(
        FakeGmailClient(inbox=[_raw("g-parent")]),
        db_session,
        storage_dir=str(attachments_dir),
        scanner=NoOpScanner(),
    )
    email = db_session.query(Email).filter(Email.gmail_id == "g-parent").one()
    parent = User(
        email=f"padre-{uuid.uuid4()}@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.post(f"/emails/{email.id}/reprocess", headers=_auth(parent))

    assert response.status_code == 403

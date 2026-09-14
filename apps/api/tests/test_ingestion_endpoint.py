import base64
from unittest.mock import MagicMock, patch

from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.user import User, UserRole
from security import create_access_token, hash_password

FACTURA_TEXTO = """
FACTURA
Factura Nº: INV-2026-001
Fecha: 01/09/2026
NIF: B12345678
Total: 45,00 EUR
""".encode()


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _staff(db_session) -> User:
    staff = User(
        email="staff-ingestion@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    return staff


def _payload() -> dict:
    return {
        "emails": [
            {
                "gmail_id": "msg-ingestion-1",
                "subject": "Tu factura de transporte",
                "from_address": "admin@crm-transporte.local",
                "attachments": [
                    {
                        "filename": "factura.pdf",
                        "mime_type": "application/pdf",
                        "content_base64": base64.b64encode(FACTURA_TEXTO).decode(),
                    }
                ],
            }
        ]
    }


def _mock_clamd_clean():
    mock_client = MagicMock()
    mock_client.instream.return_value = {"stream": ("OK", None)}
    return mock_client


def test_staff_can_run_ingestion_and_it_creates_a_pending_family_invoice(client, db_session):
    staff = _staff(db_session)
    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp

    with (
        patch("routers.ingestion.clamd.ClamdNetworkSocket", return_value=_mock_clamd_clean()),
        patch("smtplib.SMTP", return_value=mock_smtp),
    ):
        response = client.post("/ingestion/run", json=_payload(), headers=_auth_header(staff))

    assert response.status_code == 200
    assert response.json() == {"processed": 1, "skipped_already_processed": 0, "failed": []}
    invoice = db_session.query(FamilyInvoice).one()
    assert invoice.status == FamilyInvoiceStatus.PENDING_REVIEW


def test_ingestion_still_succeeds_when_smtp_is_unreachable(client, db_session):
    """El aviso por email no es un control de seguridad (a diferencia del
    antivirus): si Mailpit no responde, la ingesta sigue funcionando.
    """
    staff = _staff(db_session)

    with (
        patch("routers.ingestion.clamd.ClamdNetworkSocket", return_value=_mock_clamd_clean()),
        patch("smtplib.SMTP", side_effect=ConnectionRefusedError()),
    ):
        response = client.post("/ingestion/run", json=_payload(), headers=_auth_header(staff))

    assert response.status_code == 200
    assert response.json()["processed"] == 1


def test_ingestion_fails_closed_when_clamav_is_unreachable(client, db_session):
    """RULE-016: si el antivirus no responde, no se degrada en silencio a
    'sin escanear' — falla con un error claro en vez de aceptar adjuntos sin
    control alguno.
    """
    staff = _staff(db_session)

    with patch("routers.ingestion.clamd.ClamdNetworkSocket", side_effect=ConnectionRefusedError()):
        response = client.post("/ingestion/run", json=_payload(), headers=_auth_header(staff))

    assert response.status_code == 503
    assert db_session.query(FamilyInvoice).count() == 0


def test_parent_cannot_run_ingestion(client, db_session):
    parent = User(
        email="padre-ingestion@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.post("/ingestion/run", json=_payload(), headers=_auth_header(parent))

    assert response.status_code == 403


def test_staff_can_run_demo_inbox(client, db_session):
    staff = _staff(db_session)
    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp

    with (
        patch("routers.ingestion.clamd.ClamdNetworkSocket", return_value=_mock_clamd_clean()),
        patch("smtplib.SMTP", return_value=mock_smtp),
    ):
        response = client.post(
            "/ingestion/run",
            json={"use_demo_inbox": True},
            headers=_auth_header(staff),
        )

    assert response.status_code == 200
    assert response.json()["processed"] == 1
    invoice = db_session.query(FamilyInvoice).one()
    assert invoice.status == FamilyInvoiceStatus.PENDING_REVIEW
    assert invoice.amount is not None
    assert str(invoice.amount) == "45.00"


def test_invalid_base64_attachment_is_a_clean_400(client, db_session):
    staff = _staff(db_session)
    payload = _payload()
    payload["emails"][0]["attachments"][0]["content_base64"] = "no-es-base64-valido!!"

    response = client.post("/ingestion/run", json=payload, headers=_auth_header(staff))

    assert response.status_code == 400

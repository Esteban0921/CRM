"""Regresiones del outbox de notificaciones (TASK-0104, TASK-0105).

Cuatro cosas que la auditoria midio y que fallaban a la vez porque el envio
ocurria dentro del request:

1. Con el SMTP caido la factura quedaba publicada y el aviso se perdia en
   silencio (`except OSError: pass`), sin registro ni reintento.
2. Rebotar el estado de una factura reenviaba el correo: tres rebotes, tres
   correos al mismo padre.
3. Dos clics en «Recordatorios de vencimiento» mandaban dos correos identicos
   a 90 ms de distancia.
4. Con Mailpit apagado la API respondia `{"sent": 1, "families": 37}`: cero
   correos, y 36 familias sin usuario padre contadas como exito.
"""

import datetime
import uuid
from decimal import Decimal

from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.notification_outbox import NotificationOutbox, NotificationStatus
from models.user import User, UserRole
from notifications.email_sender import NoOpEmailSender
from notifications.outbox import MAX_ATTEMPTS, flush
from security import create_access_token, hash_password


class _BrokenSender:
    """SMTP que revienta, como Mailpit apagado."""

    def __init__(self) -> None:
        self.intentos = 0

    def send(self, *, to: str, subject: str, body: str) -> None:
        self.intentos += 1
        raise ConnectionRefusedError("SMTP no disponible")


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


def _family_con_padre(db_session, email: str) -> Family:
    family = Family(name=f"Familia {uuid.uuid4().hex[:6]}")
    db_session.add(family)
    db_session.commit()
    db_session.add(
        User(
            family_id=family.id,
            email=email,
            password_hash=hash_password("x"),
            name="Padre",
            role=UserRole.PARENT,
        )
    )
    db_session.commit()
    return family


def _invoice(db_session, family, status=FamilyInvoiceStatus.PENDING_REVIEW):
    email = Email(gmail_id=f"g-{uuid.uuid4()}")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id, document_type=DocumentType.FAMILY_INVOICE, file_path="f.pdf"
    )
    db_session.add(document)
    db_session.commit()
    invoice = FamilyInvoice(
        document_id=document.id,
        family_id=family.id if family else None,
        status=status,
        amount=Decimal("45.00"),
        issue_date=datetime.date(2026, 9, 1),
    )
    db_session.add(invoice)
    db_session.commit()
    return invoice


# --- 1. El aviso ya no se pierde con el SMTP caido ------------------------


def test_publicar_con_smtp_caido_deja_el_aviso_encolado(client, db_session):
    staff = _staff(db_session)
    family = _family_con_padre(db_session, "padre.smtp@example.com")
    invoice = _invoice(db_session, family)

    response = client.patch(
        f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"}
    )

    assert response.status_code == 200
    filas = db_session.query(NotificationOutbox).all()
    assert len(filas) == 1
    assert filas[0].recipient == "padre.smtp@example.com"
    assert filas[0].status == NotificationStatus.PENDING

    # El SMTP sigue caido: no se marca nada como enviado y queda el motivo.
    roto = _BrokenSender()
    resultado = flush(db_session, roto)
    assert resultado.sent == 0
    assert resultado.failed == 1
    assert db_session.query(NotificationOutbox).one().last_error is not None

    # Cuando vuelve, el aviso sale. Antes no habia nada que reintentar.
    bueno = NoOpEmailSender()
    resultado = flush(db_session, bueno)
    assert resultado.sent == 1
    assert [mail.to for mail in bueno.sent] == ["padre.smtp@example.com"]
    assert db_session.query(NotificationOutbox).one().status == NotificationStatus.SENT


def test_sin_transporte_no_se_marca_nada_como_enviado(client, db_session):
    staff = _staff(db_session)
    family = _family_con_padre(db_session, "padre.sin@example.com")
    invoice = _invoice(db_session, family)
    client.patch(f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"})

    resultado = flush(db_session, None)

    assert resultado.sent == 0
    assert resultado.pending == 1
    assert resultado.errors, "el flush debe decir por que no salio nada"
    assert db_session.query(NotificationOutbox).one().status == NotificationStatus.PENDING


def test_una_fila_deja_de_reintentarse_tras_el_tope(client, db_session):
    staff = _staff(db_session)
    family = _family_con_padre(db_session, "padre.tope@example.com")
    invoice = _invoice(db_session, family)
    client.patch(f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"})

    roto = _BrokenSender()
    for _ in range(MAX_ATTEMPTS + 3):
        flush(db_session, roto)

    fila = db_session.query(NotificationOutbox).one()
    assert fila.attempts == MAX_ATTEMPTS
    assert fila.status == NotificationStatus.FAILED
    assert roto.intentos == MAX_ATTEMPTS, "seguia reintentando sin freno"


# --- 2. Rebotar el estado no reenvia el correo ----------------------------


def test_rebotar_el_estado_no_reenvia_el_aviso(client, db_session):
    """El disparo era «el estado anterior era pending_review y ahora no», y
    como se podia volver a pending_review, era reutilizable: tres rebotes,
    tres correos.
    """
    staff = _staff(db_session)
    family = _family_con_padre(db_session, "padre.rebote@example.com")
    invoice = _invoice(db_session, family)

    for _ in range(3):
        client.patch(
            f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"}
        )
        client.patch(
            f"/family-invoices/{invoice.id}",
            headers=_auth(staff),
            json={"status": "pending_review"},
        )
    client.patch(f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"})

    sender = NoOpEmailSender()
    flush(db_session, sender)

    assert len(sender.sent) == 1, f"se mandaron {len(sender.sent)} correos por la misma factura"


# --- 3. Doble clic en recordatorios ---------------------------------------


def test_dos_clics_en_recordatorios_no_mandan_dos_correos(client, db_session):
    staff = _staff(db_session)
    family = _family_con_padre(db_session, "padre.doble@example.com")
    invoice = _invoice(db_session, family, status=FamilyInvoiceStatus.OVERDUE)
    _ = invoice

    primera = client.post("/notifications/overdue-reminders", headers=_auth(staff))
    segunda = client.post("/notifications/overdue-reminders", headers=_auth(staff))

    assert primera.json()["queued"] == 1
    assert segunda.json()["queued"] == 0
    assert segunda.json()["already_queued"] == 1

    sender = NoOpEmailSender()
    flush(db_session, sender)
    assert len(sender.sent) == 1


# --- 4. La respuesta deja de mentir ---------------------------------------


def test_una_familia_sin_destinatario_no_cuenta_como_exito(client, db_session):
    """5 familias con deuda, 1 correo: las otras 4 no tenian usuario padre y la
    respuesta no lo distinguia de un envio correcto.
    """
    staff = _staff(db_session)
    con_padre = _family_con_padre(db_session, "padre.unico@example.com")
    _invoice(db_session, con_padre, status=FamilyInvoiceStatus.OVERDUE)
    for _ in range(3):
        huerfana = Family(name=f"Familia sin padre {uuid.uuid4().hex[:6]}")
        db_session.add(huerfana)
        db_session.commit()
        _invoice(db_session, huerfana, status=FamilyInvoiceStatus.OVERDUE)

    body = client.post("/notifications/overdue-reminders", headers=_auth(staff)).json()

    assert body["families"] == 4
    assert body["queued"] == 1
    assert body["families_without_recipient"] == 3


def test_el_flush_dice_si_hay_transporte(client, db_session):
    staff = _staff(db_session)

    response = client.post("/notifications/flush", headers=_auth(staff))

    assert response.status_code == 200
    assert "transport_available" in response.json()


def test_staff_ve_la_bandeja_y_el_padre_no(client, db_session):
    staff = _staff(db_session)
    family = _family_con_padre(db_session, "padre.bandeja@example.com")
    invoice = _invoice(db_session, family)
    client.patch(f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"})

    listado = client.get("/notifications/outbox", headers=_auth(staff))
    assert listado.status_code == 200
    assert len(listado.json()) == 1
    assert listado.json()[0]["recipient"] == "padre.bandeja@example.com"

    parent = db_session.query(User).filter(User.role == UserRole.PARENT).first()
    assert client.get("/notifications/outbox", headers=_auth(parent)).status_code == 403


def test_una_factura_sin_familia_no_encola_nada(client, db_session):
    staff = _staff(db_session)
    invoice = _invoice(db_session, None)

    client.patch(f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"})

    assert db_session.query(NotificationOutbox).count() == 0

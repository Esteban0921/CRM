import uuid

from models.audit_log import AuditedEntityType, AuditLog
from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _make_invoice(db_session, family_id=None, confidence=0.5) -> FamilyInvoice:
    # uuid4 en vez de un timestamp: dos llamadas seguidas pueden caer en el
    # mismo tick de reloj (sobre todo en Windows) y violar el unique de
    # gmail_id — se observo como fallo intermitente real en esta sesion.
    email = Email(gmail_id=f"gmail-{uuid.uuid4()}")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id, document_type=DocumentType.FAMILY_INVOICE, file_path="f.pdf"
    )
    db_session.add(document)
    db_session.commit()
    invoice = FamilyInvoice(document_id=document.id, family_id=family_id, confidence=confidence)
    db_session.add(invoice)
    db_session.commit()
    return invoice


def test_staff_sees_all_family_invoices(client, db_session):
    family = Family(name="Familia A")
    db_session.add(family)
    db_session.commit()
    _make_invoice(db_session, family_id=family.id)
    _make_invoice(db_session, family_id=None)
    staff = User(
        email="staff@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get("/family-invoices", headers=_auth_header(staff))

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_parent_only_sees_own_family_invoices(client, db_session):
    family_a = Family(name="Familia A")
    family_b = Family(name="Familia B")
    db_session.add_all([family_a, family_b])
    db_session.commit()
    _make_invoice(db_session, family_id=family_a.id)
    _make_invoice(db_session, family_id=family_b.id)
    _make_invoice(db_session, family_id=None)  # sin enlazar: tampoco es de nadie
    parent_a = User(
        family_id=family_a.id,
        email="padre.a@example.com",
        password_hash=hash_password("x"),
        name="Padre A",
        role=UserRole.PARENT,
    )
    db_session.add(parent_a)
    db_session.commit()

    response = client.get("/family-invoices", headers=_auth_header(parent_a))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["family_id"] == str(family_a.id)


def test_parent_cannot_read_unlinked_invoice_by_id(client, db_session):
    invoice = _make_invoice(db_session, family_id=None)
    family = Family(name="Familia C")
    db_session.add(family)
    db_session.commit()
    parent = User(
        family_id=family.id,
        email="padre.c@example.com",
        password_hash=hash_password("x"),
        name="Padre C",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get(f"/family-invoices/{invoice.id}", headers=_auth_header(parent))

    assert response.status_code == 404


def test_parent_cannot_patch_invoice(client, db_session):
    family = Family(name="Familia D")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id)
    parent = User(
        family_id=family.id,
        email="padre.d@example.com",
        password_hash=hash_password("x"),
        name="Padre D",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.patch(
        f"/family-invoices/{invoice.id}", json={"status": "paid"}, headers=_auth_header(parent)
    )

    assert response.status_code == 403


def test_staff_can_link_invoice_to_family_and_it_is_audited(client, db_session):
    invoice = _make_invoice(db_session, family_id=None)
    family = Family(name="Familia E")
    db_session.add(family)
    db_session.commit()
    staff = User(
        email="staff2@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.patch(
        f"/family-invoices/{invoice.id}",
        json={"family_id": str(family.id), "status": "sent"},
        headers=_auth_header(staff),
    )

    assert response.status_code == 200
    assert response.json()["family_id"] == str(family.id)
    assert response.json()["status"] == "sent"
    logs = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_type == AuditedEntityType.FAMILY_INVOICE)
        .all()
    )
    fields_changed = {log.field_name for log in logs}
    assert fields_changed == {"family_id", "status"}


def test_review_queue_orders_lowest_confidence_first(client, db_session):
    _make_invoice(db_session, confidence=0.9)
    _make_invoice(db_session, confidence=0.2)
    _make_invoice(db_session, confidence=0.6)
    staff = User(
        email="staff3@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get("/family-invoices", headers=_auth_header(staff))

    confidences = [row["confidence"] for row in response.json()]
    assert confidences == sorted(confidences)


def test_list_and_get_include_resolved_family_name(client, db_session):
    """El tablero kanban (frontend) necesita un nombre legible, no solo el
    UUID de family_id, para poder mostrar la tarjeta de cada factura.
    """
    family = Family(name="Familia Kanban")
    db_session.add(family)
    db_session.commit()
    linked = _make_invoice(db_session, family_id=family.id)
    unlinked = _make_invoice(db_session, family_id=None)
    staff = User(
        email="staff5@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    list_response = client.get("/family-invoices", headers=_auth_header(staff)).json()
    listed = {row["id"]: row for row in list_response}
    fetched = client.get(f"/family-invoices/{linked.id}", headers=_auth_header(staff)).json()

    assert listed[str(linked.id)]["family_name"] == "Familia Kanban"
    assert listed[str(unlinked.id)]["family_name"] is None
    assert fetched["family_name"] == "Familia Kanban"


def test_filter_by_status(client, db_session):
    invoice = _make_invoice(db_session)
    invoice.status = FamilyInvoiceStatus.PAID
    db_session.commit()
    _make_invoice(db_session)  # queda pending_review
    staff = User(
        email="staff4@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get("/family-invoices?status=paid", headers=_auth_header(staff))

    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "paid"

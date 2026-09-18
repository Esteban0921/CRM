import datetime
import uuid
from decimal import Decimal

from models.audit_log import AuditedEntityType, AuditLog
from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.task import Task, TaskStatus
from models.user import User, UserRole
from notifications.email_sender import NoOpEmailSender
from notifications.outbox import flush
from notifications.service import PAYMENT_CLAIM_TITLE
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _make_invoice(
    db_session,
    family_id=None,
    confidence=0.5,
    status=FamilyInvoiceStatus.PENDING_REVIEW,
    amount=Decimal("45.00"),
    issue_date=datetime.date(2026, 9, 1),
) -> FamilyInvoice:
    """Una factura de prueba nace completa.

    Hasta TASK-0101 se podia publicar una sin importe ni fecha de emision, y
    varios tests lo hacian: reproducian el bug en vez de comprobar el producto.
    """
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
    invoice = FamilyInvoice(
        document_id=document.id,
        family_id=family_id,
        confidence=confidence,
        status=status,
        amount=amount,
        issue_date=issue_date,
    )
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


def test_staff_can_filter_invoices_by_family_id(client, db_session):
    family_a = Family(name="Familia Filtro A")
    family_b = Family(name="Familia Filtro B")
    db_session.add_all([family_a, family_b])
    db_session.commit()
    _make_invoice(db_session, family_id=family_a.id, status=FamilyInvoiceStatus.SENT)
    _make_invoice(db_session, family_id=family_b.id, status=FamilyInvoiceStatus.SENT)
    staff = User(
        email="staff-filtro@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    parent = User(
        family_id=family_a.id,
        email="padre-filtro@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add_all([staff, parent])
    db_session.commit()

    as_staff = client.get(f"/family-invoices?family_id={family_a.id}", headers=_auth_header(staff))
    as_parent = client.get(
        f"/family-invoices?family_id={family_b.id}", headers=_auth_header(parent)
    )

    assert as_staff.status_code == 200
    assert len(as_staff.json()) == 1
    assert as_staff.json()[0]["family_id"] == str(family_a.id)
    assert as_parent.status_code == 200
    assert len(as_parent.json()) == 1
    assert as_parent.json()[0]["family_id"] == str(family_a.id)


def test_parent_only_sees_own_family_invoices(client, db_session):
    family_a = Family(name="Familia A")
    family_b = Family(name="Familia B")
    db_session.add_all([family_a, family_b])
    db_session.commit()
    _make_invoice(db_session, family_id=family_a.id, status=FamilyInvoiceStatus.SENT)
    _make_invoice(db_session, family_id=family_a.id)  # pending_review: RULE-017, el padre no la ve
    _make_invoice(db_session, family_id=family_b.id, status=FamilyInvoiceStatus.SENT)
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
    assert body[0]["status"] == "sent"


def test_parent_cannot_read_own_pending_review_invoice(client, db_session):
    family = Family(name="Familia pendiente")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id)
    parent = User(
        family_id=family.id,
        email="padre.pending@example.com",
        password_hash=hash_password("x"),
        name="Padre Pending",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    listed = client.get("/family-invoices", headers=_auth_header(parent))
    fetched = client.get(f"/family-invoices/{invoice.id}", headers=_auth_header(parent))

    assert listed.status_code == 200
    assert listed.json() == []
    assert fetched.status_code == 404


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
    assert {"family_id", "status"}.issubset(fields_changed)


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


def test_publishing_a_reviewed_invoice_notifies_parents(client, db_session):
    family = Family(name="Familia Aviso")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id)
    db_session.add(
        User(
            family_id=family.id,
            email="padre.aviso@example.com",
            password_hash=hash_password("x"),
            name="Padre Aviso",
            role=UserRole.PARENT,
        )
    )
    staff = User(
        email="staff-aviso@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    response = client.patch(
        f"/family-invoices/{invoice.id}",
        json={"status": "sent"},
        headers=_auth_header(staff),
    )

    assert response.status_code == 200
    # Publicar ENCOLA; el envio ocurre al vaciar la bandeja (TASK-0104). Asi
    # una caida del SMTP no puede hacer que el padre se quede sin enterarse.
    sender = NoOpEmailSender()
    flush(db_session, sender)
    assert [mail.to for mail in sender.sent] == ["padre.aviso@example.com"]


def test_assigning_family_without_publishing_does_not_notify(client, db_session):
    family = Family(name="Familia Silencio")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=None)
    db_session.add(
        User(
            family_id=family.id,
            email="padre.silencio@example.com",
            password_hash=hash_password("x"),
            name="Padre Silencio",
            role=UserRole.PARENT,
        )
    )
    staff = User(
        email="staff-silencio@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    response = client.patch(
        f"/family-invoices/{invoice.id}",
        json={"family_id": str(family.id)},
        headers=_auth_header(staff),
    )
    sender = NoOpEmailSender()
    flush(db_session, sender)

    assert response.status_code == 200
    assert sender.sent == []


def test_sent_invoice_with_past_due_date_is_promoted_to_overdue(client, db_session):
    import datetime

    family = Family(name="Familia Vence")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id, status=FamilyInvoiceStatus.SENT)
    invoice.due_date = datetime.date(2020, 1, 1)
    db_session.commit()
    staff = User(
        email="staff-overdue@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get("/family-invoices", headers=_auth_header(staff))

    assert response.status_code == 200
    listed = {row["id"]: row for row in response.json()}
    assert listed[str(invoice.id)]["status"] == "overdue"
    db_session.refresh(invoice)
    assert invoice.status == FamilyInvoiceStatus.OVERDUE


def test_cannot_publish_invoice_without_family(client, db_session):
    invoice = _make_invoice(db_session, family_id=None)
    staff = User(
        email="staff-huerfana@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.patch(
        f"/family-invoices/{invoice.id}",
        json={"status": "sent"},
        headers=_auth_header(staff),
    )

    assert response.status_code == 422
    db_session.refresh(invoice)
    assert invoice.status == FamilyInvoiceStatus.PENDING_REVIEW


def test_publishing_sets_due_date_in_thirty_days_when_missing(client, db_session):
    family = Family(name="Familia Plazo")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id)
    staff = User(
        email="staff-plazo@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.patch(
        f"/family-invoices/{invoice.id}",
        json={"status": "sent"},
        headers=_auth_header(staff),
    )

    assert response.status_code == 200
    assert response.json()["due_date"] is not None


def test_bulk_assign_and_publish_reuses_single_invoice_rules(client, db_session):
    family = Family(name="Familia Lote")
    db_session.add(family)
    db_session.commit()
    linked = _make_invoice(db_session, family_id=family.id)
    orphan = _make_invoice(db_session, family_id=None)
    staff = User(
        email="staff-lote@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    parent = User(
        family_id=family.id,
        email="padre-lote@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add_all([staff, parent])
    db_session.commit()

    published = client.post(
        "/family-invoices/bulk",
        json={"ids": [str(linked.id), str(orphan.id)], "status": "sent"},
        headers=_auth_header(staff),
    )
    assigned = client.post(
        "/family-invoices/bulk",
        json={"ids": [str(orphan.id)], "family_id": str(family.id)},
        headers=_auth_header(staff),
    )
    as_parent = client.post(
        "/family-invoices/bulk",
        json={"ids": [str(linked.id)], "status": "paid"},
        headers=_auth_header(parent),
    )

    assert published.status_code == 200
    assert published.json()["updated"] == 1
    assert published.json()["failed"][0]["id"] == str(orphan.id)
    assert assigned.status_code == 200
    assert assigned.json() == {"updated": 1, "failed": []}
    assert as_parent.status_code == 403
    db_session.refresh(linked)
    db_session.refresh(orphan)
    assert linked.status == FamilyInvoiceStatus.SENT
    assert orphan.family_id == family.id
    assert orphan.status == FamilyInvoiceStatus.PENDING_REVIEW


def test_parent_claim_payment_creates_task_without_marking_paid(client, db_session):
    family = Family(name="Familia Pago")
    other = Family(name="Familia Ajena")
    db_session.add_all([family, other])
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id, status=FamilyInvoiceStatus.SENT)
    pending = _make_invoice(db_session, family_id=family.id)
    paid = _make_invoice(db_session, family_id=family.id, status=FamilyInvoiceStatus.PAID)
    parent = User(
        family_id=family.id,
        email="padre-pago@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    stranger = User(
        family_id=other.id,
        email="padre-ajeno@example.com",
        password_hash=hash_password("x"),
        name="Ajeno",
        role=UserRole.PARENT,
    )
    staff = User(
        email="staff-pago@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add_all([parent, stranger, staff])
    db_session.commit()

    created = client.post(
        f"/family-invoices/{invoice.id}/claim-payment",
        headers=_auth_header(parent),
    )
    duplicate = client.post(
        f"/family-invoices/{invoice.id}/claim-payment",
        headers=_auth_header(parent),
    )
    hidden = client.post(
        f"/family-invoices/{pending.id}/claim-payment",
        headers=_auth_header(parent),
    )
    already_paid = client.post(
        f"/family-invoices/{paid.id}/claim-payment",
        headers=_auth_header(parent),
    )
    other_family = client.post(
        f"/family-invoices/{invoice.id}/claim-payment",
        headers=_auth_header(stranger),
    )
    as_staff = client.post(
        f"/family-invoices/{invoice.id}/claim-payment",
        headers=_auth_header(staff),
    )

    assert created.status_code == 201
    assert created.json()["title"] == PAYMENT_CLAIM_TITLE
    assert created.json()["family_name"] == "Familia Pago"
    assert created.json()["status"] == "pending"
    assert f"invoice:{invoice.id}" in created.json()["description"]
    assert duplicate.status_code == 409
    assert hidden.status_code == 404
    assert already_paid.status_code == 409
    assert other_family.status_code == 404
    assert as_staff.status_code == 403
    db_session.refresh(invoice)
    assert invoice.status == FamilyInvoiceStatus.SENT
    tasks = (
        db_session.query(Task)
        .filter(Task.family_id == family.id, Task.status == TaskStatus.PENDING)
        .all()
    )
    assert len(tasks) == 1


def test_confirm_payment_marks_paid_and_closes_claim(client, db_session):
    family = Family(name="Familia Cobro")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id, status=FamilyInvoiceStatus.SENT)
    pending = _make_invoice(db_session, family_id=family.id)
    parent = User(
        family_id=family.id,
        email="padre-cobro@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    staff = User(
        email="staff-cobro@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add_all([parent, staff])
    db_session.commit()
    claimed = client.post(
        f"/family-invoices/{invoice.id}/claim-payment",
        headers=_auth_header(parent),
    )
    assert claimed.status_code == 201

    confirmed = client.post(
        f"/family-invoices/{invoice.id}/confirm-payment",
        headers=_auth_header(staff),
    )
    as_parent = client.post(
        f"/family-invoices/{invoice.id}/confirm-payment",
        headers=_auth_header(parent),
    )
    hidden = client.post(
        f"/family-invoices/{pending.id}/confirm-payment",
        headers=_auth_header(staff),
    )
    again = client.post(
        f"/family-invoices/{invoice.id}/confirm-payment",
        headers=_auth_header(staff),
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "paid"
    assert as_parent.status_code == 403
    assert hidden.status_code == 422
    assert again.status_code == 409
    db_session.refresh(invoice)
    assert invoice.status == FamilyInvoiceStatus.PAID
    task = db_session.get(Task, uuid.UUID(claimed.json()["id"]))
    assert task is not None
    assert task.status == TaskStatus.DONE


def test_parent_list_hides_extracted_data(client, db_session):
    family = Family(name="Familia OCR")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id, status=FamilyInvoiceStatus.SENT)
    invoice.extracted_data = {"student_name": "Menor", "total_amount": "45,00"}
    db_session.commit()
    parent = User(
        family_id=family.id,
        email="padre-ocr@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    staff = User(
        email="staff-ocr@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add_all([parent, staff])
    db_session.commit()

    as_parent = client.get("/family-invoices", headers=_auth_header(parent)).json()
    as_staff = client.get("/family-invoices", headers=_auth_header(staff)).json()
    exported = client.get(f"/families/{family.id}/export", headers=_auth_header(parent)).json()

    assert as_parent[0]["extracted_data"] is None
    assert as_staff[0]["extracted_data"]["student_name"] == "Menor"
    assert exported["family_invoices"][0]["extracted_data"] is None


def test_invoice_list_includes_queue_and_overdue_age(client, db_session):
    import datetime

    family = Family(name="Familia Edad")
    db_session.add(family)
    db_session.commit()
    pending = _make_invoice(db_session, family_id=family.id)
    pending.created_at = datetime.datetime(2026, 9, 1, tzinfo=datetime.UTC)
    overdue = _make_invoice(db_session, family_id=family.id, status=FamilyInvoiceStatus.OVERDUE)
    overdue.due_date = datetime.date(2026, 9, 1)
    db_session.commit()
    staff = User(
        email="staff-edad@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    listed = {
        row["id"]: row for row in client.get("/family-invoices", headers=_auth_header(staff)).json()
    }
    assert listed[str(pending.id)]["days_in_queue"] is not None
    assert listed[str(pending.id)]["days_in_queue"] >= 0
    assert listed[str(overdue.id)]["days_overdue"] is not None
    assert listed[str(overdue.id)]["days_overdue"] >= 0

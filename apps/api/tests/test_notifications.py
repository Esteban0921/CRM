import uuid
from datetime import date
from decimal import Decimal

from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.notification_outbox import NotificationOutbox
from models.user import User, UserRole
from notifications.email_sender import NoOpEmailSender
from notifications.outbox import flush
from notifications.service import (
    notify_due_soon_invoices,
    notify_new_family_invoice,
    notify_overdue_invoices,
)
from security import create_access_token, hash_password


def _make_invoice(db_session, family_id=None, amount=None) -> FamilyInvoice:
    email = Email(gmail_id=f"gmail-{uuid.uuid4()}")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id, document_type=DocumentType.FAMILY_INVOICE, file_path="f.pdf"
    )
    db_session.add(document)
    db_session.commit()
    invoice = FamilyInvoice(document_id=document.id, family_id=family_id, amount=amount)
    db_session.add(invoice)
    db_session.commit()
    return invoice


def _outbox(db_session, status=None):
    query = db_session.query(NotificationOutbox)
    if status is not None:
        query = query.filter(NotificationOutbox.status == status)
    return query.all()


def _drain(db_session):
    """Encolar y vaciar: el flush es el unico que toca el SMTP (TASK-0105)."""
    sender = NoOpEmailSender()
    flush(db_session, sender)
    return sender


def test_notifies_all_parents_of_the_linked_family(db_session):
    family = Family(name="Familia Notif")
    db_session.add(family)
    db_session.commit()
    db_session.add_all(
        [
            User(
                family_id=family.id,
                email="padre1@example.com",
                password_hash=hash_password("x"),
                name="P1",
                role=UserRole.PARENT,
            ),
            User(
                family_id=family.id,
                email="padre2@example.com",
                password_hash=hash_password("x"),
                name="P2",
                role=UserRole.PARENT,
            ),
        ]
    )
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id, amount=Decimal("45.00"))
    notify_new_family_invoice(db_session, invoice)
    db_session.commit()
    sender = _drain(db_session)

    recipients = {sent.to for sent in sender.sent}
    assert recipients == {"padre1@example.com", "padre2@example.com"}
    assert "45.00" in sender.sent[0].body


def test_does_not_notify_when_invoice_is_unlinked(db_session):
    invoice = _make_invoice(db_session, family_id=None)
    notify_new_family_invoice(db_session, invoice)
    db_session.commit()

    assert _outbox(db_session) == []


def test_does_not_notify_when_family_has_no_parent_users_yet(db_session):
    family = Family(name="Familia Sin Padres")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id)
    notify_new_family_invoice(db_session, invoice)
    db_session.commit()

    assert _outbox(db_session) == []


def test_overdue_reminder_emails_parents_and_skips_pending_review(db_session):
    family = Family(name="Familia Vencida")
    db_session.add(family)
    db_session.commit()
    db_session.add(
        User(
            family_id=family.id,
            email="padre.vencido@example.com",
            password_hash=hash_password("x"),
            name="Padre",
            role=UserRole.PARENT,
        )
    )
    overdue = _make_invoice(db_session, family_id=family.id, amount=Decimal("45.00"))
    overdue.status = FamilyInvoiceStatus.SENT
    overdue.due_date = date(2020, 1, 1)
    pending = _make_invoice(db_session, family_id=family.id, amount=Decimal("99.00"))
    pending.status = FamilyInvoiceStatus.PENDING_REVIEW
    db_session.commit()
    outcome = notify_overdue_invoices(db_session)
    db_session.commit()
    sent, families = outcome.queued, outcome.families
    sender = _drain(db_session)

    assert sent == 1
    assert families == 1
    assert sender.sent[0].to == "padre.vencido@example.com"
    assert "45.00" in sender.sent[0].body
    assert "99.00" not in sender.sent[0].body


def test_staff_can_trigger_overdue_reminders_endpoint(client, db_session):
    family = Family(name="Familia Endpoint")
    db_session.add(family)
    db_session.commit()
    db_session.add(
        User(
            family_id=family.id,
            email="padre.endpoint@example.com",
            password_hash=hash_password("x"),
            name="Padre",
            role=UserRole.PARENT,
        )
    )
    invoice = _make_invoice(db_session, family_id=family.id, amount=Decimal("12.00"))
    invoice.status = FamilyInvoiceStatus.OVERDUE
    staff = User(
        email="staff-rem@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    token = create_access_token(user_id=staff.id, role=staff.role.value, family_id=None)

    response = client.post(
        "/notifications/overdue-reminders",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "queued": 1,
        "already_queued": 0,
        "families": 1,
        "families_without_recipient": 0,
        "pending_in_outbox": 1,
    }
    sender = _drain(db_session)
    assert sender.sent[0].to == "padre.endpoint@example.com"


def test_due_soon_reminder_skips_pending_review(db_session):
    from datetime import timedelta

    family = Family(name="Familia Pronto")
    db_session.add(family)
    db_session.commit()
    db_session.add(
        User(
            family_id=family.id,
            email="padre.pronto@example.com",
            password_hash=hash_password("x"),
            name="Padre",
            role=UserRole.PARENT,
        )
    )
    upcoming = _make_invoice(db_session, family_id=family.id, amount=Decimal("45.00"))
    upcoming.status = FamilyInvoiceStatus.SENT
    upcoming.due_date = date.today() + timedelta(days=3)
    pending = _make_invoice(db_session, family_id=family.id, amount=Decimal("99.00"))
    pending.status = FamilyInvoiceStatus.PENDING_REVIEW
    pending.due_date = date.today() + timedelta(days=2)
    db_session.commit()
    outcome = notify_due_soon_invoices(db_session)
    db_session.commit()
    sent, families = outcome.queued, outcome.families
    sender = _drain(db_session)

    assert sent == 1
    assert families == 1
    assert sender.sent[0].to == "padre.pronto@example.com"
    assert "45.00" in sender.sent[0].body
    assert "99.00" not in sender.sent[0].body


def test_staff_inbox_lists_pending_work_and_parent_is_forbidden(client, db_session):
    family = Family(name="Familia Inbox")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id, amount=Decimal("12.00"))
    invoice.status = FamilyInvoiceStatus.PENDING_REVIEW
    db_session.commit()
    staff = User(
        email="staff-inbox@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    parent = User(
        family_id=family.id,
        email="padre-inbox@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add_all([staff, parent])
    db_session.commit()

    as_staff = client.get("/notifications/inbox", headers=_auth_header(staff))
    as_parent = client.get("/notifications/inbox", headers=_auth_header(parent))
    due_soon = client.post(
        "/notifications/due-soon-reminders",
        headers=_auth_header(parent),
    )

    assert as_staff.status_code == 200
    kinds = {item["kind"] for item in as_staff.json()}
    assert "pending_review" in kinds
    assert as_parent.status_code == 403
    assert due_soon.status_code == 403


def test_staff_can_trigger_due_soon_reminders_endpoint(client, db_session):
    from datetime import timedelta

    family = Family(name="Familia Siete")
    db_session.add(family)
    db_session.commit()
    db_session.add(
        User(
            family_id=family.id,
            email="padre.siete@example.com",
            password_hash=hash_password("x"),
            name="Padre",
            role=UserRole.PARENT,
        )
    )
    invoice = _make_invoice(db_session, family_id=family.id, amount=Decimal("20.00"))
    invoice.status = FamilyInvoiceStatus.SENT
    invoice.due_date = date.today() + timedelta(days=4)
    staff = User(
        email="staff-siete@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.post(
        "/notifications/due-soon-reminders",
        headers=_auth_header(staff),
    )

    assert response.status_code == 200
    assert response.json() == {
        "queued": 1,
        "already_queued": 0,
        "families": 1,
        "families_without_recipient": 0,
        "pending_in_outbox": 1,
    }
    sender = _drain(db_session)
    assert sender.sent[0].to == "padre.siete@example.com"


def test_parent_mine_inbox_hides_pending_review(client, db_session):
    from datetime import timedelta

    family = Family(name="Familia Avisos")
    db_session.add(family)
    db_session.commit()
    parent = User(
        family_id=family.id,
        email="padre-avisos@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    staff = User(
        email="staff-avisos@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add_all([parent, staff])
    overdue = _make_invoice(db_session, family_id=family.id, amount=Decimal("20.00"))
    overdue.status = FamilyInvoiceStatus.OVERDUE
    overdue.due_date = date(2020, 1, 1)
    pending = _make_invoice(db_session, family_id=family.id, amount=Decimal("99.00"))
    pending.status = FamilyInvoiceStatus.PENDING_REVIEW
    pending.due_date = date.today() + timedelta(days=2)
    soon = _make_invoice(db_session, family_id=family.id, amount=Decimal("15.00"))
    soon.status = FamilyInvoiceStatus.SENT
    soon.due_date = date.today() + timedelta(days=3)
    db_session.commit()

    as_parent = client.get("/notifications/mine", headers=_auth_header(parent))
    as_staff = client.get("/notifications/mine", headers=_auth_header(staff))
    staff_inbox = client.get("/notifications/inbox", headers=_auth_header(parent))

    assert as_parent.status_code == 200
    kinds = {item["kind"]: item["count"] for item in as_parent.json()}
    assert kinds["overdue"] == 1
    assert kinds["due_soon"] == 1
    assert "pending_review" not in kinds
    assert as_staff.status_code == 403
    assert staff_inbox.status_code == 403


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}

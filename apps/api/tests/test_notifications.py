import datetime
from decimal import Decimal

from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice
from models.user import User, UserRole
from notifications.email_sender import NoOpEmailSender
from notifications.service import notify_new_family_invoice
from security import hash_password


def _make_invoice(db_session, family_id=None, amount=None) -> FamilyInvoice:
    email = Email(gmail_id=f"gmail-{datetime.datetime.now(datetime.UTC).timestamp()}")
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
    sender = NoOpEmailSender()

    notify_new_family_invoice(db_session, sender, invoice)

    recipients = {sent.to for sent in sender.sent}
    assert recipients == {"padre1@example.com", "padre2@example.com"}
    assert "45.00" in sender.sent[0].body


def test_does_not_notify_when_invoice_is_unlinked(db_session):
    invoice = _make_invoice(db_session, family_id=None)
    sender = NoOpEmailSender()

    notify_new_family_invoice(db_session, sender, invoice)

    assert sender.sent == []


def test_does_not_notify_when_family_has_no_parent_users_yet(db_session):
    family = Family(name="Familia Sin Padres")
    db_session.add(family)
    db_session.commit()
    invoice = _make_invoice(db_session, family_id=family.id)
    sender = NoOpEmailSender()

    notify_new_family_invoice(db_session, sender, invoice)

    assert sender.sent == []

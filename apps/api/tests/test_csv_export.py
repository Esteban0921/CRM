from decimal import Decimal

from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _invoice(db_session, family_id, status, amount="40.00"):
    email = Email(gmail_id=f"csv-{status}-{amount}")
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
        status=status,
        amount=Decimal(amount),
    )
    db_session.add(invoice)
    db_session.commit()
    return invoice


def test_staff_csv_includes_pending_review(client, db_session):
    family = Family(name="Familia CSV")
    db_session.add(family)
    db_session.commit()
    _invoice(db_session, family.id, FamilyInvoiceStatus.PENDING_REVIEW)
    _invoice(db_session, family.id, FamilyInvoiceStatus.SENT, "55.00")
    staff = User(
        email="staff-csv@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get("/family-invoices/export.csv", headers=_auth_header(staff))

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    body = response.text
    assert "pending_review" in body
    assert "sent" in body
    assert "Familia CSV" in body


def test_parent_csv_excludes_pending_review(client, db_session):
    family = Family(name="Familia CSV Padre")
    db_session.add(family)
    db_session.commit()
    _invoice(db_session, family.id, FamilyInvoiceStatus.PENDING_REVIEW, "99.00")
    _invoice(db_session, family.id, FamilyInvoiceStatus.SENT, "40.00")
    parent = User(
        family_id=family.id,
        email="padre-csv@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get("/family-invoices/export.csv", headers=_auth_header(parent))

    assert response.status_code == 200
    assert "pending_review" not in response.text
    assert "40.00" in response.text
    assert "99.00" not in response.text

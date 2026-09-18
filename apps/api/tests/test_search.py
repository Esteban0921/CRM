from decimal import Decimal

from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.student import Student
from models.supplier import Supplier
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def test_staff_search_finds_family_student_invoice_and_supplier(client, db_session):
    family = Family(name="Familia Busqueda")
    db_session.add(family)
    db_session.commit()
    db_session.add(Student(family_id=family.id, name="Ana Busqueda", school="Colegio Norte"))
    db_session.add(Supplier(name="Taller Busqueda", email="taller@example.com"))
    email = Email(gmail_id="search-mail")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id, document_type=DocumentType.FAMILY_INVOICE, file_path="f.pdf"
    )
    db_session.add(document)
    db_session.commit()
    db_session.add(
        FamilyInvoice(
            document_id=document.id,
            family_id=family.id,
            amount=Decimal("45.00"),
            status=FamilyInvoiceStatus.SENT,
        )
    )
    staff = User(
        email="staff-search@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get("/search", params={"q": "Busqueda"}, headers=_auth_header(staff))

    assert response.status_code == 200
    types = {hit["type"] for hit in response.json()["hits"]}
    assert types == {"family", "student", "family_invoice", "supplier"}


def test_parent_cannot_search(client, db_session):
    parent = User(
        email="padre-search@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get("/search", params={"q": "Ana"}, headers=_auth_header(parent))
    assert response.status_code == 403


def test_search_rejects_short_query(client, db_session):
    staff = User(
        email="staff-short@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get("/search", params={"q": "a"}, headers=_auth_header(staff))
    assert response.status_code == 422

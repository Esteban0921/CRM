import uuid

from models.document import Document, DocumentType
from models.email import Email
from models.supplier import Supplier
from models.supplier_invoice import SupplierInvoice
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _make_invoice(db_session) -> SupplierInvoice:
    email = Email(gmail_id=f"gmail-{uuid.uuid4()}")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id, document_type=DocumentType.SUPPLIER_INVOICE, file_path="g.pdf"
    )
    db_session.add(document)
    db_session.commit()
    invoice = SupplierInvoice(document_id=document.id)
    db_session.add(invoice)
    db_session.commit()
    return invoice


def test_parent_cannot_list_supplier_invoices(client, db_session):
    parent = User(
        email="padre@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get("/supplier-invoices", headers=_auth_header(parent))

    assert response.status_code == 403


def test_staff_can_list_and_update_supplier_invoices(client, db_session):
    invoice = _make_invoice(db_session)
    staff = User(
        email="staff@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    listed = client.get("/supplier-invoices", headers=_auth_header(staff))
    updated = client.patch(
        f"/supplier-invoices/{invoice.id}", json={"status": "approved"}, headers=_auth_header(staff)
    )

    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert updated.status_code == 200
    assert updated.json()["status"] == "approved"


def test_staff_can_list_suppliers_parent_cannot(client, db_session):
    db_session.add(Supplier(name="Gasoleos del Sur", email="facturas@gasoleos.example"))
    parent = User(
        email="padre-sup@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    staff = User(
        email="staff-sup@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add_all([parent, staff])
    db_session.commit()

    as_staff = client.get("/suppliers", headers=_auth_header(staff))
    as_parent = client.get("/suppliers", headers=_auth_header(parent))

    assert as_staff.status_code == 200
    assert as_staff.json()[0]["name"] == "Gasoleos del Sur"
    assert as_parent.status_code == 403

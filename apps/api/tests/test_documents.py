from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _stored_invoice(db_session, tmp_path, *, family_id, status):
    path = tmp_path / "factura.pdf"
    path.write_bytes(b"%PDF-demo")
    email = Email(gmail_id="doc-mail")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id,
        document_type=DocumentType.FAMILY_INVOICE,
        file_path=str(path),
        original_filename="factura.pdf",
        mime_type="application/pdf",
    )
    db_session.add(document)
    db_session.commit()
    invoice = FamilyInvoice(document_id=document.id, family_id=family_id, status=status)
    db_session.add(invoice)
    db_session.commit()
    return document, invoice


def test_staff_can_download_invoice_file(client, db_session, tmp_path):
    family = Family(name="Familia Doc")
    db_session.add(family)
    db_session.commit()
    document, _invoice = _stored_invoice(
        db_session, tmp_path, family_id=family.id, status=FamilyInvoiceStatus.PENDING_REVIEW
    )
    staff = User(
        email="staff-doc@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get(f"/documents/{document.id}/file", headers=_auth_header(staff))

    assert response.status_code == 200
    assert response.content == b"%PDF-demo"
    assert "factura.pdf" in response.headers.get("content-disposition", "")


def test_parent_can_download_published_own_invoice(client, db_session, tmp_path):
    family = Family(name="Familia Doc 2")
    db_session.add(family)
    db_session.commit()
    document, _invoice = _stored_invoice(
        db_session, tmp_path, family_id=family.id, status=FamilyInvoiceStatus.SENT
    )
    parent = User(
        family_id=family.id,
        email="padre-doc@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get(f"/documents/{document.id}/file", headers=_auth_header(parent))

    assert response.status_code == 200
    assert response.content == b"%PDF-demo"


def test_parent_cannot_download_pending_review_file(client, db_session, tmp_path):
    family = Family(name="Familia Doc 3")
    db_session.add(family)
    db_session.commit()
    document, _invoice = _stored_invoice(
        db_session, tmp_path, family_id=family.id, status=FamilyInvoiceStatus.PENDING_REVIEW
    )
    parent = User(
        family_id=family.id,
        email="padre-doc3@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get(f"/documents/{document.id}/file", headers=_auth_header(parent))

    assert response.status_code == 404


def test_parent_cannot_download_other_family_file(client, db_session, tmp_path):
    family_a = Family(name="A")
    family_b = Family(name="B")
    db_session.add_all([family_a, family_b])
    db_session.commit()
    document, _invoice = _stored_invoice(
        db_session, tmp_path, family_id=family_a.id, status=FamilyInvoiceStatus.SENT
    )
    parent = User(
        family_id=family_b.id,
        email="padre-b@example.com",
        password_hash=hash_password("x"),
        name="Padre B",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get(f"/documents/{document.id}/file", headers=_auth_header(parent))

    assert response.status_code == 404


def test_staff_can_list_credit_notes(client, db_session):
    email = Email(gmail_id="credit-mail")
    db_session.add(email)
    db_session.commit()
    db_session.add(
        Document(
            email_id=email.id,
            document_type=DocumentType.CREDIT_NOTE,
            file_path="abono.pdf",
            original_filename="abono.pdf",
        )
    )
    db_session.add(
        Document(
            email_id=email.id,
            document_type=DocumentType.FAMILY_INVOICE,
            file_path="factura.pdf",
            original_filename="factura.pdf",
        )
    )
    db_session.commit()
    staff = User(
        email="staff-docs@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get(
        "/documents", params={"document_type": "credit_note"}, headers=_auth_header(staff)
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["document_type"] == "credit_note"


def test_parent_cannot_list_documents(client, db_session):
    parent = User(
        email="padre-docs@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get("/documents", headers=_auth_header(parent))
    assert response.status_code == 403


def test_document_download_rejects_relative_path_escape(client, db_session, tmp_path, monkeypatch):
    store = tmp_path / "store"
    store.mkdir()
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"%PDF-secret")
    monkeypatch.setattr("routers.documents.settings.attachments_dir", str(store))
    email = Email(gmail_id="escape-mail")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id,
        document_type=DocumentType.FAMILY_INVOICE,
        file_path="../secret.pdf",
        original_filename="factura.pdf",
        mime_type="application/pdf",
    )
    db_session.add(document)
    db_session.commit()
    staff = User(
        email="staff-escape@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get(f"/documents/{document.id}/file", headers=_auth_header(staff))
    assert response.status_code == 404

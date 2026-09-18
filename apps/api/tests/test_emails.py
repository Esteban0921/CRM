from models.document import Document, DocumentType
from models.email import Email, EmailProcessingStatus
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def test_staff_lists_ingested_emails_with_document_count(client, db_session):
    email = Email(
        gmail_id="inbox-1",
        subject="Factura septiembre",
        from_address="admin@crm-transporte.local",
        processing_status=EmailProcessingStatus.PROCESSED,
    )
    db_session.add(email)
    db_session.commit()
    db_session.add(
        Document(
            email_id=email.id,
            document_type=DocumentType.FAMILY_INVOICE,
            file_path="f.pdf",
        )
    )
    staff = User(
        email="staff-mail@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get("/emails", headers=_auth_header(staff))

    assert response.status_code == 200
    assert response.json()[0]["subject"] == "Factura septiembre"
    assert response.json()[0]["document_count"] == 1


def test_parent_cannot_list_emails(client, db_session):
    parent = User(
        email="padre-mail@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get("/emails", headers=_auth_header(parent))
    assert response.status_code == 403

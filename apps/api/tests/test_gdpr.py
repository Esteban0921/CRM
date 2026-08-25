import datetime
from decimal import Decimal

from models.audit_log import AuditedEntityType, AuditLog
from models.contract import Contract
from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice
from models.student import Student
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _seed_full_family(db_session) -> Family:
    family = Family(name="Familia Export", address="Calle Falsa 123")
    db_session.add(family)
    db_session.commit()
    student = Student(family_id=family.id, name="Alumno Export", school="Colegio X")
    db_session.add(student)
    db_session.commit()
    contract = Contract(
        student_id=student.id,
        service_type="ruta",
        monthly_fee=Decimal("40.00"),
        start_date=datetime.date(2026, 9, 1),
    )
    email = Email(gmail_id="gmail-export")
    db_session.add_all([contract, email])
    db_session.commit()
    document = Document(
        email_id=email.id, document_type=DocumentType.FAMILY_INVOICE, file_path="f.pdf"
    )
    db_session.add(document)
    db_session.commit()
    db_session.add(
        FamilyInvoice(document_id=document.id, family_id=family.id, amount=Decimal("40.00"))
    )
    db_session.commit()
    return family


def test_staff_can_export_full_family_data(client, db_session):
    family = _seed_full_family(db_session)
    staff = User(
        email="staff@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get(f"/families/{family.id}/export", headers=_auth_header(staff))

    assert response.status_code == 200
    body = response.json()
    assert body["family"]["name"] == "Familia Export"
    assert len(body["students"]) == 1
    assert len(body["contracts"]) == 1
    assert len(body["family_invoices"]) == 1


def test_parent_can_export_own_family_data(client, db_session):
    family = _seed_full_family(db_session)
    parent = User(
        family_id=family.id,
        email="padre@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get(f"/families/{family.id}/export", headers=_auth_header(parent))

    assert response.status_code == 200


def test_parent_cannot_export_another_familys_data(client, db_session):
    family = _seed_full_family(db_session)
    other_family = Family(name="Otra Familia")
    db_session.add(other_family)
    db_session.commit()
    parent = User(
        family_id=other_family.id,
        email="padre2@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get(f"/families/{family.id}/export", headers=_auth_header(parent))

    assert response.status_code == 404


def test_staff_can_anonymize_a_family(client, db_session):
    family = _seed_full_family(db_session)
    student_id = db_session.query(Student).filter(Student.family_id == family.id).one().id
    parent = User(
        family_id=family.id,
        email="padre3@example.com",
        password_hash=hash_password("x"),
        name="Padre Real",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()
    staff = User(
        email="staff2@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.post(f"/families/{family.id}/anonymize", headers=_auth_header(staff))

    assert response.status_code == 204
    db_session.expire_all()
    updated_family = db_session.get(Family, family.id)
    updated_student = db_session.get(Student, student_id)
    updated_parent = db_session.get(User, parent.id)
    assert updated_family.name != "Familia Export"
    assert updated_family.address is None
    assert updated_student.name != "Alumno Export"
    assert updated_student.school is None
    assert updated_parent.email != "padre3@example.com"
    # Los registros de facturacion se conservan (obligacion contable).
    assert db_session.query(FamilyInvoice).filter(FamilyInvoice.family_id == family.id).count() == 1
    logs = db_session.query(AuditLog).filter(AuditLog.entity_type == AuditedEntityType.FAMILY).all()
    assert any(log.field_name == "name" for log in logs)


def test_parent_cannot_anonymize(client, db_session):
    family = _seed_full_family(db_session)
    parent = User(
        family_id=family.id,
        email="padre4@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.post(f"/families/{family.id}/anonymize", headers=_auth_header(parent))

    assert response.status_code == 403

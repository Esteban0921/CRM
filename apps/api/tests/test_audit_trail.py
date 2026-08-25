import datetime
from decimal import Decimal

from models.audit_log import AuditedEntityType, AuditLog
from models.contract import Contract
from models.family import Family
from models.student import Student
from models.user import User, UserRole
from security import create_access_token, hash_password


def _staff_header(db_session) -> dict[str, str]:
    staff = User(
        email="staff@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    token = create_access_token(user_id=staff.id, role=staff.role.value, family_id=None)
    return {"Authorization": f"Bearer {token}"}, staff


def test_updating_a_family_records_audit_log(client, db_session):
    family = Family(name="Familia Original")
    db_session.add(family)
    db_session.commit()
    headers, staff = _staff_header(db_session)

    response = client.patch(
        f"/families/{family.id}", json={"name": "Familia Corregida"}, headers=headers
    )

    assert response.status_code == 200
    entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_type == AuditedEntityType.FAMILY, AuditLog.entity_id == family.id)
        .one()
    )
    assert entry.field_name == "name"
    assert entry.old_value == "Familia Original"
    assert entry.new_value == "Familia Corregida"
    assert entry.edited_by == staff.id


def test_updating_a_student_records_audit_log(client, db_session):
    family = Family(name="Familia X")
    db_session.add(family)
    db_session.commit()
    student = Student(family_id=family.id, name="Alumno Original")
    db_session.add(student)
    db_session.commit()
    headers, _ = _staff_header(db_session)

    client.patch(f"/students/{student.id}", json={"name": "Alumno Corregido"}, headers=headers)

    entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_type == AuditedEntityType.STUDENT, AuditLog.entity_id == student.id)
        .one()
    )
    assert entry.old_value == "Alumno Original"
    assert entry.new_value == "Alumno Corregido"


def test_updating_a_contract_records_audit_log(client, db_session):
    family = Family(name="Familia Y")
    db_session.add(family)
    db_session.commit()
    student = Student(family_id=family.id, name="Alumno Y")
    db_session.add(student)
    db_session.commit()
    contract = Contract(
        student_id=student.id,
        service_type="ruta",
        monthly_fee=Decimal("40.00"),
        start_date=datetime.date(2026, 9, 1),
    )
    db_session.add(contract)
    db_session.commit()
    headers, _ = _staff_header(db_session)

    client.patch(f"/contracts/{contract.id}", json={"monthly_fee": "45.00"}, headers=headers)

    entry = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_type == AuditedEntityType.CONTRACT, AuditLog.entity_id == contract.id
        )
        .one()
    )
    assert entry.field_name == "monthly_fee"


def test_no_op_update_does_not_create_audit_log(client, db_session):
    family = Family(name="Sin Cambios")
    db_session.add(family)
    db_session.commit()
    headers, _ = _staff_header(db_session)

    client.patch(f"/families/{family.id}", json={"name": "Sin Cambios"}, headers=headers)

    assert db_session.query(AuditLog).count() == 0

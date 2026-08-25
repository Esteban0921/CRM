import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from models.contract import Contract, ContractStatus
from models.family import Family
from models.student import Student
from models.user import User, UserRole


def test_family_with_student_and_contract_round_trips(db_session):
    family = Family(name="Familia Garcia")
    student = Student(family=family, name="Ana Garcia", birth_date=datetime.date(2015, 3, 1))
    contract = Contract(
        student=student,
        service_type="ruta_manana",
        monthly_fee=Decimal("45.00"),
        start_date=datetime.date(2026, 9, 1),
    )
    db_session.add(family)
    db_session.commit()

    stored_family = db_session.get(Family, family.id)
    assert stored_family.students[0].name == "Ana Garcia"
    assert stored_family.students[0].contracts[0].status == ContractStatus.ACTIVE
    assert contract.monthly_fee == Decimal("45.00")


def test_parent_user_is_scoped_to_a_family(db_session):
    family = Family(name="Familia Lopez")
    parent = User(
        family=family,
        email="padre@example.com",
        password_hash="hashed",
        name="Padre Lopez",
        role=UserRole.PARENT,
    )
    db_session.add(family)
    db_session.commit()

    assert parent.family_id == family.id
    assert family.users[0].role == UserRole.PARENT


def test_staff_user_has_no_family(db_session):
    staff = User(
        email="staff@example.com",
        password_hash="hashed",
        name="Equipo Interno",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    assert staff.family_id is None


def test_duplicate_email_is_rejected(db_session):
    db_session.add(
        User(email="dup@example.com", password_hash="a", name="Uno", role=UserRole.STAFF)
    )
    db_session.commit()

    db_session.add(
        User(email="dup@example.com", password_hash="b", name="Dos", role=UserRole.STAFF)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()

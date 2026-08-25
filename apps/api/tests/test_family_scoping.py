import datetime
from decimal import Decimal

from models.contract import Contract
from models.family import Family
from models.student import Student
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _seed_two_families(db_session):
    family_a = Family(name="Familia A")
    family_b = Family(name="Familia B")
    student_a = Student(family=family_a, name="Alumno A")
    student_b = Student(family=family_b, name="Alumno B")
    contract_a = Contract(
        student=student_a,
        service_type="ruta",
        monthly_fee=Decimal("40.00"),
        start_date=datetime.date(2026, 9, 1),
    )
    contract_b = Contract(
        student=student_b,
        service_type="ruta",
        monthly_fee=Decimal("40.00"),
        start_date=datetime.date(2026, 9, 1),
    )
    parent_a = User(
        family=family_a,
        email="padre.a@example.com",
        password_hash=hash_password("x"),
        name="Padre A",
        role=UserRole.PARENT,
    )
    staff = User(
        email="staff@example.com",
        password_hash=hash_password("x"),
        name="Equipo",
        role=UserRole.STAFF,
    )
    db_session.add_all([family_a, family_b, parent_a, staff])
    db_session.commit()
    return {
        "family_a": family_a,
        "family_b": family_b,
        "student_a": student_a,
        "student_b": student_b,
        "contract_a": contract_a,
        "contract_b": contract_b,
        "parent_a": parent_a,
        "staff": staff,
    }


def test_parent_cannot_read_another_familys_family(client, db_session):
    seed = _seed_two_families(db_session)

    response = client.get(
        f"/families/{seed['family_b'].id}", headers=_auth_header(seed["parent_a"])
    )

    assert response.status_code == 404


def test_parent_can_read_own_family(client, db_session):
    seed = _seed_two_families(db_session)

    response = client.get(
        f"/families/{seed['family_a'].id}", headers=_auth_header(seed["parent_a"])
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(seed["family_a"].id)


def test_parent_students_list_is_forced_to_own_family_even_if_other_id_requested(
    client, db_session
):
    seed = _seed_two_families(db_session)

    response = client.get(
        "/students",
        params={"family_id": str(seed["family_b"].id)},
        headers=_auth_header(seed["parent_a"]),
    )

    assert response.status_code == 200
    names = [s["name"] for s in response.json()]
    assert names == ["Alumno A"]


def test_parent_cannot_read_another_familys_student(client, db_session):
    seed = _seed_two_families(db_session)

    response = client.get(
        f"/students/{seed['student_b'].id}", headers=_auth_header(seed["parent_a"])
    )

    assert response.status_code == 404


def test_parent_cannot_read_another_familys_contract(client, db_session):
    seed = _seed_two_families(db_session)

    response = client.get(
        f"/contracts/{seed['contract_b'].id}", headers=_auth_header(seed["parent_a"])
    )

    assert response.status_code == 404


def test_parent_contracts_list_only_includes_own_family(client, db_session):
    seed = _seed_two_families(db_session)

    response = client.get("/contracts", headers=_auth_header(seed["parent_a"]))

    assert response.status_code == 200
    ids = [c["id"] for c in response.json()]
    assert ids == [str(seed["contract_a"].id)]


def test_parent_cannot_create_family(client, db_session):
    seed = _seed_two_families(db_session)

    response = client.post(
        "/families", json={"name": "Nueva"}, headers=_auth_header(seed["parent_a"])
    )

    assert response.status_code == 403


def test_staff_can_read_any_family(client, db_session):
    seed = _seed_two_families(db_session)

    response = client.get(f"/families/{seed['family_b'].id}", headers=_auth_header(seed["staff"]))

    assert response.status_code == 200


def test_unauthenticated_request_is_rejected(client, db_session):
    seed = _seed_two_families(db_session)

    response = client.get(f"/families/{seed['family_a'].id}")

    assert response.status_code == 401

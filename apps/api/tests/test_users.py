from models.family import Family
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
    return {"Authorization": f"Bearer {token}"}


def test_staff_can_create_parent_user_for_a_family(client, db_session):
    family = Family(name="Familia Nueva")
    db_session.add(family)
    db_session.commit()
    headers = _staff_header(db_session)

    response = client.post(
        "/users",
        json={
            "email": "padre@example.com",
            "password": "claveSegura123",
            "name": "Nuevo Padre",
            "role": "parent",
            "family_id": str(family.id),
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "parent"
    assert body["family_id"] == str(family.id)
    assert "password" not in body
    assert "password_hash" not in body


def test_creating_parent_without_family_id_is_rejected(client, db_session):
    headers = _staff_header(db_session)

    response = client.post(
        "/users",
        json={
            "email": "padre2@example.com",
            "password": "claveSegura123",
            "name": "Sin Familia",
            "role": "parent",
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_duplicate_email_returns_conflict(client, db_session):
    headers = _staff_header(db_session)
    payload = {
        "email": "duplicado@example.com",
        "password": "claveSegura123",
        "name": "Uno",
        "role": "staff",
    }

    first = client.post("/users", json=payload, headers=headers)
    second = client.post("/users", json={**payload, "name": "Dos"}, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 409

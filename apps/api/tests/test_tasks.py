from models.family import Family
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def test_staff_can_create_and_complete_a_task(client, db_session):
    family = Family(name="Familia Tarea")
    db_session.add(family)
    db_session.commit()
    staff = User(
        email="staff@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    created = client.post(
        "/tasks",
        json={
            "family_id": str(family.id),
            "title": "Contactar por impago",
            "due_date": "2026-09-15",
        },
        headers=_auth_header(staff),
    )
    task_id = created.json()["id"]
    updated = client.patch(
        f"/tasks/{task_id}", json={"status": "done"}, headers=_auth_header(staff)
    )

    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    assert created.json()["family_name"] == "Familia Tarea"
    assert updated.json()["status"] == "done"


def test_parent_cannot_create_tasks(client, db_session):
    family = Family(name="Familia Tarea 2")
    db_session.add(family)
    db_session.commit()
    parent = User(
        family_id=family.id,
        email="padre@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.post(
        "/tasks",
        json={"family_id": str(family.id), "title": "intento"},
        headers=_auth_header(parent),
    )

    assert response.status_code == 403


def test_tasks_are_ordered_by_due_date_with_no_due_date_last(client, db_session):
    family = Family(name="Familia Tarea 3")
    db_session.add(family)
    db_session.commit()
    staff = User(
        email="staff2@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    headers = _auth_header(staff)
    client.post("/tasks", json={"family_id": str(family.id), "title": "Sin fecha"}, headers=headers)
    client.post(
        "/tasks",
        json={"family_id": str(family.id), "title": "Urgente", "due_date": "2026-09-01"},
        headers=headers,
    )

    response = client.get("/tasks", headers=headers)

    titles = [t["title"] for t in response.json()]
    assert titles == ["Urgente", "Sin fecha"]


def test_filter_tasks_by_family(client, db_session):
    family_a = Family(name="Familia A")
    family_b = Family(name="Familia B")
    db_session.add_all([family_a, family_b])
    db_session.commit()
    staff = User(
        email="staff3@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    headers = _auth_header(staff)
    client.post("/tasks", json={"family_id": str(family_a.id), "title": "A"}, headers=headers)
    client.post("/tasks", json={"family_id": str(family_b.id), "title": "B"}, headers=headers)

    response = client.get("/tasks", params={"family_id": str(family_a.id)}, headers=headers)

    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "A"

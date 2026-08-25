from models.family import Family
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def test_staff_can_create_and_list_notes_for_a_family(client, db_session):
    family = Family(name="Familia Nota")
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
        "/notes",
        json={
            "entity_type": "family",
            "entity_id": str(family.id),
            "body": "Recoge sola los viernes",
        },
        headers=_auth_header(staff),
    )
    listed = client.get(
        "/notes",
        params={"entity_type": "family", "entity_id": str(family.id)},
        headers=_auth_header(staff),
    )

    assert created.status_code == 201
    assert created.json()["created_by"] == str(staff.id)
    assert len(listed.json()) == 1
    assert listed.json()[0]["body"] == "Recoge sola los viernes"


def test_parent_cannot_create_notes(client, db_session):
    family = Family(name="Familia Nota 2")
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
        "/notes",
        json={"entity_type": "family", "entity_id": str(family.id), "body": "intento"},
        headers=_auth_header(parent),
    )

    assert response.status_code == 403


def test_staff_can_delete_a_note(client, db_session):
    family = Family(name="Familia Nota 3")
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
    created = client.post(
        "/notes",
        json={"entity_type": "family", "entity_id": str(family.id), "body": "borrar esto"},
        headers=_auth_header(staff),
    )
    note_id = created.json()["id"]

    response = client.delete(f"/notes/{note_id}", headers=_auth_header(staff))
    listed = client.get(
        "/notes",
        params={"entity_type": "family", "entity_id": str(family.id)},
        headers=_auth_header(staff),
    )

    assert response.status_code == 204
    assert listed.json() == []

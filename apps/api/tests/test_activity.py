from models.family import Family
from models.note import Note, NoteEntityType
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def test_staff_sees_audit_and_notes_in_family_activity(client, db_session):
    family = Family(name="Familia Historial")
    db_session.add(family)
    db_session.commit()
    staff = User(
        email="staff-hist@example.com",
        password_hash=hash_password("x"),
        name="Staff Hist",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    headers = _auth_header(staff)
    client.patch(f"/families/{family.id}", json={"address": "Calle Nueva 1"}, headers=headers)
    db_session.add(
        Note(
            entity_type=NoteEntityType.FAMILY,
            entity_id=family.id,
            body="Llamar el lunes",
            created_by=staff.id,
        )
    )
    db_session.commit()

    response = client.get(f"/families/{family.id}/activity", headers=headers)

    assert response.status_code == 200
    titles = [event["title"] for event in response.json()]
    assert any(title.startswith("Familia:") for title in titles)
    assert "Nota interna" in titles
    assert any(
        event["detail"] and "Llamar el lunes" in event["detail"] for event in response.json()
    )


def test_parent_cannot_read_family_activity(client, db_session):
    family = Family(name="Familia Privada")
    db_session.add(family)
    db_session.commit()
    parent = User(
        family_id=family.id,
        email="padre-hist@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get(f"/families/{family.id}/activity", headers=_auth_header(parent))
    assert response.status_code == 403

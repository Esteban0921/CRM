from models.supplier import Supplier, SupplierCategory
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _staff(db_session) -> User:
    staff = User(
        email="staff-sup@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    return staff


def test_staff_can_create_and_update_supplier(client, db_session):
    headers = _auth_header(_staff(db_session))

    created = client.post(
        "/suppliers",
        json={"name": "Repsol", "email": "Facturas@repsol.com", "category": "fuel"},
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "facturas@repsol.com"
    assert body["category"] == "fuel"

    updated = client.patch(
        f"/suppliers/{body['id']}",
        json={"name": "Repsol Comercial"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Repsol Comercial"
    listed = client.get("/suppliers", headers=headers)
    assert len(listed.json()) == 1


def test_parent_cannot_create_supplier(client, db_session):
    parent = User(
        email="padre-sup@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.post(
        "/suppliers",
        json={"name": "Taller"},
        headers=_auth_header(parent),
    )
    assert response.status_code == 403
    assert db_session.query(Supplier).count() == 0


def test_update_missing_supplier_is_404(client, db_session):
    headers = _auth_header(_staff(db_session))
    response = client.patch(
        "/suppliers/11111111-1111-1111-1111-111111111111",
        json={"name": "Nadie"},
        headers=headers,
    )
    assert response.status_code == 404
    assert SupplierCategory.OTHER.value == "other"

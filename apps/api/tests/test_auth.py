from models.family import Family
from models.user import User, UserRole
from security import hash_password


def _create_parent(db_session, email="padre@example.com", password="claveSegura123"):
    family = Family(name="Familia Test")
    user = User(
        family=family,
        email=email,
        password_hash=hash_password(password),
        name="Padre Test",
        role=UserRole.PARENT,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_login_with_correct_credentials_returns_token(client, db_session):
    _create_parent(db_session, email="padre@example.com", password="claveSegura123")

    response = client.post(
        "/auth/login", json={"email": "padre@example.com", "password": "claveSegura123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 0


def test_login_with_wrong_password_is_rejected(client, db_session):
    _create_parent(db_session, email="padre@example.com", password="claveSegura123")

    response = client.post(
        "/auth/login", json={"email": "padre@example.com", "password": "incorrecta"}
    )

    assert response.status_code == 401


def test_login_with_unknown_email_is_rejected(client, db_session):
    response = client.post(
        "/auth/login", json={"email": "no-existe@example.com", "password": "algo"}
    )

    assert response.status_code == 401

from db import get_db
from main import app


class _FailingSession:
    def execute(self, *_args, **_kwargs):
        raise RuntimeError("database down")

    def close(self) -> None:
        return None


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_database_is_down(client):
    app.dependency_overrides[get_db] = lambda: _FailingSession()

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Base de datos no disponible"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from config import settings
from db import Base, get_db
from main import app


@pytest.fixture
def db_session():
    # StaticPool + check_same_thread=False: TestClient sirve las requests en
    # otro hilo: sin esto, SQLite en memoria falla o ve una BD vacia.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def attachments_dir(tmp_path, monkeypatch):
    """Directorio de adjuntos aislado por test.

    `GET /documents/{id}/file` solo sirve ficheros contenidos en
    `ATTACHMENTS_DIR`; un test que escriba fuera no representa lo que hace el
    pipeline y antes pasaba solo porque la contencion no se aplicaba a rutas
    absolutas (TASK-0091).
    """
    storage = tmp_path / "attachments"
    storage.mkdir()
    monkeypatch.setattr(settings, "attachments_dir", str(storage))
    return storage


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    """El limitador de login vive en memoria del proceso (TASK-0094): sin
    limpiarlo, los intentos fallidos de un test bloquean al siguiente.
    """
    from routers.auth import login_limiter

    login_limiter.clear()
    yield
    login_limiter.clear()

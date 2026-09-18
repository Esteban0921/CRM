from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


def _engine_kwargs(url: str) -> dict:
    """Timeout corto en Postgres: sin esto, un Docker caído deja cada request
    colgada decenas de segundos (el TCP retry de Windows). Los tests usan su
    propio engine SQLite en conftest, no este.
    """
    # hide_parameters: sin esto SQLAlchemy adjunta la sentencia Y los parametros
    # al mensaje de la excepcion, asi que un INSERT fallido de `students` imprime
    # el nombre, la fecha de nacimiento y el colegio de un menor en el log
    # (RULE-015, TASK-0093).
    base = {"hide_parameters": True}
    if url.startswith("sqlite"):
        return {**base, "connect_args": {"check_same_thread": False}}
    if "postgres" in url:
        return {**base, "pool_pre_ping": True, "connect_args": {"connect_timeout": 3}}
    return {**base, "pool_pre_ping": True}


engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

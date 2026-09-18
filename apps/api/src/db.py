from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


def _engine_kwargs(url: str) -> dict:
    """Timeout corto en Postgres: sin esto, un Docker caído deja cada request
    colgada decenas de segundos (el TCP retry de Windows). Los tests usan su
    propio engine SQLite en conftest, no este.
    """
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    if "postgres" in url:
        return {"pool_pre_ping": True, "connect_args": {"connect_timeout": 3}}
    return {"pool_pre_ping": True}


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

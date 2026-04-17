"""SQLAlchemy engine and session (PostgreSQL when DATABASE_URL is set)."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings

engine = None
SessionLocal: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    pass


def configure_db() -> None:
    global engine, SessionLocal
    if not settings.database_url:
        return
    if engine is None:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    configure_db()
    if engine is None:
        return
    import backend.models  # noqa: F401 — register models

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    from fastapi import status

    from backend.errors import ServiceError

    configure_db()
    if SessionLocal is None:
        raise ServiceError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "database_not_configured",
            "Database is not configured. Set DATABASE_URL on the server.",
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

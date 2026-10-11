"""SQLAlchemy engine, session, and table initialisation."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def _make_engine():
    settings = get_settings()
    connect_args = (
        {"check_same_thread": False}
        if settings.DATABASE_URL.startswith("sqlite")
        else {}
    )
    return create_engine(settings.DATABASE_URL, connect_args=connect_args)


engine = _make_engine()

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autocommit=False, autoflush=False
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables defined in ORM models (idempotent)."""
    # Import models so SQLAlchemy registers them with Base.metadata before
    # calling create_all.
    import backend.models.models  # noqa: F401  – side-effect import

    Base.metadata.create_all(bind=engine)

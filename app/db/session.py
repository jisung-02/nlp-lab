"""Database engine and session dependency helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, echo=False)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session."""

    with Session(engine) as session:
        yield session

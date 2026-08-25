"""Database engine and session dependency helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import event
from sqlmodel import Session, create_engine

from app.core.config import get_settings

settings = get_settings()
_is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(settings.database_url, connect_args=connect_args, echo=False)


def _tune_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Apply per-connection SQLite settings for a web workload.

    - WAL lets readers proceed while an admin write is in flight instead of
      blocking behind the writer's lock.
    - ``synchronous=NORMAL`` is durable under WAL for everything except a
      power loss mid-checkpoint and avoids an fsync per transaction.
    - ``busy_timeout`` turns a transient "database is locked" error into a
      short wait when a write and a checkpoint overlap.
    """

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA temp_store=MEMORY")
    finally:
        cursor.close()


if _is_sqlite:
    event.listen(engine, "connect", _tune_sqlite_connection)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session."""

    with Session(engine) as session:
        yield session

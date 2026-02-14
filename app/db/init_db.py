"""Database initialization utilities for local development and tests."""

from __future__ import annotations

from sqlmodel import Session, SQLModel, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import engine
from app.models import AdminUser


def create_db_and_tables() -> None:
    """Create all tables from SQLModel metadata."""

    SQLModel.metadata.create_all(engine)


def create_initial_admin() -> None:
    """Seed an initial admin user when not present."""

    settings = get_settings()

    with Session(engine) as session:
        existing_user = session.exec(
            select(AdminUser).where(AdminUser.username == settings.admin_username)
        ).first()
        if existing_user is not None:
            return

        admin_user = AdminUser(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
        )
        session.add(admin_user)
        session.commit()


def init_db() -> None:
    """Initialize tables and seed admin data."""

    create_db_and_tables()
    create_initial_admin()

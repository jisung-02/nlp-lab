"""Admin user model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, String
from sqlmodel import Field, SQLModel

from app.core.constants import utcnow


class AdminUser(SQLModel, table=True):
    """Admin credentials table."""

    __tablename__ = "admin_user"
    __table_args__ = (
        CheckConstraint("length(username) >= 4", name="ck_admin_user_username_min_len"),
    )

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(50), unique=True, nullable=False))
    password_hash: str = Field(sa_column=Column(String(255), nullable=False))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

"""Post model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, text
from sqlmodel import Field, SQLModel

from app.core.constants import utcnow


class Post(SQLModel, table=True):
    """News post table."""

    __tablename__ = "post"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(sa_column=Column(String(200), nullable=False))
    slug: str = Field(sa_column=Column(String(150), unique=True, nullable=False))
    content: str = Field(sa_column=Column(String(12000), nullable=False))
    is_published: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("1")),
    )
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=utcnow),
    )

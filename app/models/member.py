"""Member model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.core.constants import MemberRole, enum_values, utcnow


class Member(SQLModel, table=True):
    """Lab member profile table."""

    __tablename__ = "member"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(100), nullable=False))
    name_en: str | None = Field(default=None, sa_column=Column(String(100), nullable=True))
    role: MemberRole = Field(
        sa_column=Column(
            SAEnum(
                MemberRole,
                name="member_role",
                native_enum=False,
                values_callable=enum_values,
            ),
            nullable=False,
        )
    )
    email: str = Field(sa_column=Column(String(255), unique=True, nullable=False))
    photo_url: str | None = Field(default=None, sa_column=Column(String(500), nullable=True))
    bio: str | None = Field(default=None, sa_column=Column(String(2000), nullable=True))
    bio_en: str | None = Field(default=None, sa_column=Column(String(2000), nullable=True))
    display_order: int = Field(default=100, sa_column=Column(Integer, nullable=False, default=100))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=utcnow),
    )

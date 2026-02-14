"""Project model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, Date, DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

from app.core.constants import ProjectStatus, enum_values, utcnow

if TYPE_CHECKING:
    from app.models.publication import Publication


class Project(SQLModel, table=True):
    """Research project table."""

    __tablename__ = "project"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(sa_column=Column(String(200), nullable=False))
    slug: str = Field(sa_column=Column(String(150), unique=True, nullable=False))
    summary: str = Field(sa_column=Column(String(300), nullable=False))
    description: str = Field(sa_column=Column(String(8000), nullable=False))
    status: ProjectStatus = Field(
        sa_column=Column(
            SAEnum(
                ProjectStatus,
                name="project_status",
                native_enum=False,
                values_callable=enum_values,
            ),
            nullable=False,
        )
    )
    start_date: date = Field(sa_column=Column(Date, nullable=False))
    end_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=utcnow),
    )

    publications: list[Publication] = Relationship(back_populates="related_project")

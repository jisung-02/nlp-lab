"""Publication model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, Integer, String
from sqlmodel import Field, Relationship, SQLModel

from app.core.constants import utcnow

if TYPE_CHECKING:
    from app.models.project import Project


class Publication(SQLModel, table=True):
    """Research publication table."""

    __tablename__ = "publication"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(sa_column=Column(String(300), nullable=False))
    title_en: str | None = Field(default=None, sa_column=Column(String(300), nullable=True))
    authors: str = Field(sa_column=Column(String(500), nullable=False))
    authors_en: str | None = Field(default=None, sa_column=Column(String(500), nullable=True))
    venue: str = Field(sa_column=Column(String(255), nullable=False))
    venue_en: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    year: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    link: str | None = Field(default=None, sa_column=Column(String(500), nullable=True))
    related_project_id: int | None = Field(default=None, foreign_key="project.id")
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    related_project: "Project" = Relationship(back_populates="publications")

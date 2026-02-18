"""Project form schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import ProjectStatus


class ProjectBaseInput(BaseModel):
    """Shared project form fields."""

    title: str = Field(min_length=1, max_length=200)
    title_en: str | None = Field(default=None, max_length=200)
    slug: str = Field(min_length=1, max_length=150)
    summary: str = Field(min_length=1, max_length=300)
    summary_en: str | None = Field(default=None, max_length=300)
    description: str = Field(min_length=1, max_length=8000)
    description_en: str | None = Field(default=None, max_length=8000)
    status: ProjectStatus
    start_date: date
    end_date: date | None = None

    @field_validator("title", "slug", "summary", "description", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("title_en", "summary_en", "description_en", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("end_date", mode="before")
    @classmethod
    def _normalize_end_date(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @model_validator(mode="after")
    def _validate_date_range(self) -> ProjectBaseInput:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self


class ProjectCreateInput(ProjectBaseInput):
    """Project create form payload."""


class ProjectUpdateInput(ProjectBaseInput):
    """Project update form payload."""

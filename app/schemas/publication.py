"""Publication form schemas."""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


class PublicationBaseInput(BaseModel):
    """Shared publication form fields."""

    title: str = Field(min_length=1, max_length=300)
    title_en: str | None = Field(default=None, max_length=300)
    authors: str = Field(min_length=1, max_length=500)
    authors_en: str | None = Field(default=None, max_length=500)
    venue: str = Field(min_length=1, max_length=255)
    venue_en: str | None = Field(default=None, max_length=255)
    year: int = Field(ge=1900, le=3000)
    link: str | None = Field(default=None, max_length=500)
    related_project_id: int | None = None

    @field_validator("title", "authors", "venue", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("title_en", "authors_en", "venue_en", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("link", mode="before")
    @classmethod
    def _normalize_optional_link(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("link")
    @classmethod
    def _validate_link_scheme(cls, value: str | None) -> str | None:
        if value is None:
            return None

        parsed = urlsplit(value)
        if parsed.scheme:
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("link must be a valid http(s) URL")
            return value

        if value.startswith("/") and not value.startswith("//"):
            return value

        raise ValueError("link must be a valid http(s) URL or root-relative path")

    @field_validator("related_project_id", mode="before")
    @classmethod
    def _normalize_related_project(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @model_validator(mode="after")
    def _validate_related_project_id(self) -> PublicationBaseInput:
        if self.related_project_id is not None and self.related_project_id <= 0:
            raise ValueError("related_project_id must be positive")
        return self


class PublicationCreateInput(PublicationBaseInput):
    """Publication create form payload."""


class PublicationUpdateInput(PublicationBaseInput):
    """Publication update form payload."""

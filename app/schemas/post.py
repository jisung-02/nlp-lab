"""Post form schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PostBaseInput(BaseModel):
    """Shared post form fields."""

    title: str = Field(min_length=1, max_length=200)
    title_en: str | None = Field(default=None, max_length=200)
    slug: str = Field(min_length=1, max_length=150)
    content: str = Field(min_length=1, max_length=12000)
    content_en: str | None = Field(default=None, max_length=12000)
    is_published: bool = True

    @field_validator("title", "slug", "content", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("title_en", "content_en", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None


class PostCreateInput(PostBaseInput):
    """Post create form payload."""


class PostUpdateInput(PostBaseInput):
    """Post update form payload."""

"""Member form schemas."""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import MemberRole


class MemberBaseInput(BaseModel):
    """Shared member form fields."""

    name: str = Field(min_length=1, max_length=100)
    name_en: str | None = Field(default=None, max_length=100)
    role: MemberRole
    email: str = Field(min_length=3, max_length=255)
    photo_url: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=2000)
    bio_en: str | None = Field(default=None, max_length=2000)
    display_order: int = Field(default=100)

    @field_validator("name", "email", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("name_en", "photo_url", "bio", "bio_en", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("photo_url")
    @classmethod
    def _validate_photo_url_scheme(cls, value: str | None) -> str | None:
        if value is None:
            return None

        parsed = urlsplit(value)
        if parsed.scheme:
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("photo_url must be a valid http(s) URL")
            return value

        if value.startswith("/") and not value.startswith("//"):
            return value

        raise ValueError("photo_url must be a valid http(s) URL or root-relative path")

    @model_validator(mode="after")
    def _ensure_display_order(self) -> MemberBaseInput:
        if self.display_order < 0:
            raise ValueError("display_order must be zero or positive")
        return self


class MemberCreateInput(MemberBaseInput):
    """Member create form payload."""


class MemberUpdateInput(MemberBaseInput):
    """Member update form payload."""

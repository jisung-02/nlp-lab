"""Application-wide constants and shared values."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum, StrEnum


class MemberRole(StrEnum):
    """Supported member role values."""

    PROFESSOR = "professor"
    RESEARCHER = "researcher"
    PHD = "phd"
    MASTER = "master"
    UNDERGRAD = "undergrad"


class ProjectStatus(StrEnum):
    """Supported project status values."""

    ONGOING = "ongoing"
    COMPLETED = "completed"


HOME_HERO_IMAGE_POST_SLUG = "system-home-hero-image"
HOME_HERO_IMAGE_POST_TITLE = "홈 히어로 이미지"


def enum_values(enum_cls: type[Enum]) -> list[str]:
    """Return enum values for SQLAlchemy enum configuration."""

    return [str(item.value) for item in enum_cls]


def utcnow() -> datetime:
    """Return timezone-aware current UTC datetime."""

    return datetime.now(UTC)

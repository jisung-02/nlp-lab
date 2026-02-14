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


def enum_values(enum_cls: type[Enum]) -> list[str]:
    """Return enum values for SQLAlchemy enum configuration."""

    return [str(item.value) for item in enum_cls]


def utcnow() -> datetime:
    """Return timezone-aware current UTC datetime."""

    return datetime.now(UTC)

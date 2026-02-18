"""Member domain services."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError
from sqlmodel import Session

from app.models.member import Member
from app.repositories import member_repo
from app.schemas.member import MemberCreateInput, MemberUpdateInput


def parse_member_create_input(
    *,
    name: str,
    name_en: str | None,
    role: str,
    email: str,
    photo_url: str | None,
    bio: str | None,
    bio_en: str | None,
    display_order: str,
) -> MemberCreateInput | None:
    """Return validated create payload or ``None``."""

    fallback_name = name_en.strip() if isinstance(name_en, str) else ""
    resolved_name = name.strip() or fallback_name

    try:
        return MemberCreateInput.model_validate(
            {
                "name": resolved_name,
                "name_en": name_en,
                "role": role,
                "email": email,
                "photo_url": photo_url,
                "bio": bio,
                "bio_en": bio_en,
                "display_order": display_order,
            }
        )
    except ValidationError:
        return None


def parse_member_update_input(
    *,
    name: str,
    name_en: str | None,
    role: str,
    email: str,
    photo_url: str | None,
    bio: str | None,
    bio_en: str | None,
    display_order: str,
) -> MemberUpdateInput | None:
    """Return validated update payload or ``None``."""

    fallback_name = name_en.strip() if isinstance(name_en, str) else ""
    resolved_name = name.strip() or fallback_name

    try:
        return MemberUpdateInput.model_validate(
            {
                "name": resolved_name,
                "name_en": name_en,
                "role": role,
                "email": email,
                "photo_url": photo_url,
                "bio": bio,
                "bio_en": bio_en,
                "display_order": display_order,
            }
        )
    except ValidationError:
        return None


def list_members(session: Session) -> Sequence[Member]:
    """Return members for admin listing."""

    return member_repo.list_members(session)


def create_member(
    session: Session,
    input_data: MemberCreateInput,
) -> tuple[Member | None, str | None]:
    """Create a member or return a validation error message."""

    if member_repo.get_member_by_email(session, input_data.email) is not None:
        return None, "이미 사용 중인 이메일입니다."

    member = Member(
        name=input_data.name,
        name_en=input_data.name_en,
        role=input_data.role,
        email=input_data.email,
        photo_url=input_data.photo_url,
        bio=input_data.bio,
        bio_en=input_data.bio_en,
        display_order=input_data.display_order,
    )
    return member_repo.create_member(session, member), None


def update_member(
    session: Session,
    member_id: int,
    input_data: MemberUpdateInput,
) -> tuple[Member | None, str | None]:
    """Update a member or return an error message."""

    member = member_repo.get_member_by_id(session, member_id)
    if member is None:
        return None, "멤버를 찾을 수 없습니다."

    duplicate_member = member_repo.get_member_by_email(session, input_data.email)
    if duplicate_member is not None and duplicate_member.id != member.id:
        return None, "이미 사용 중인 이메일입니다."

    member.name = input_data.name
    member.name_en = input_data.name_en
    member.role = input_data.role
    member.email = input_data.email
    member.photo_url = input_data.photo_url
    member.bio = input_data.bio
    member.bio_en = input_data.bio_en
    member.display_order = input_data.display_order

    return member_repo.update_member(session, member), None


def delete_member(session: Session, member_id: int) -> str | None:
    """Delete a member or return an error message."""

    member = member_repo.get_member_by_id(session, member_id)
    if member is None:
        return "멤버를 찾을 수 없습니다."

    member_repo.delete_member(session, member)
    return None

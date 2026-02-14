"""Database access helpers for members."""

from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, col, select

from app.models.member import Member


def list_members(session: Session) -> Sequence[Member]:
    """Return all members sorted for admin listing."""

    return session.exec(
        select(Member).order_by(col(Member.display_order).asc(), col(Member.created_at).asc())
    ).all()


def get_member_by_id(session: Session, member_id: int) -> Member | None:
    """Return member by primary key."""

    return session.get(Member, member_id)


def get_member_by_email(session: Session, email: str) -> Member | None:
    """Return member by unique email."""

    return session.exec(select(Member).where(col(Member.email) == email)).first()


def create_member(session: Session, member: Member) -> Member:
    """Persist a new member."""

    session.add(member)
    session.commit()
    session.refresh(member)
    return member


def update_member(session: Session, member: Member) -> Member:
    """Persist an updated member."""

    session.add(member)
    session.commit()
    session.refresh(member)
    return member


def delete_member(session: Session, member: Member) -> None:
    """Hard-delete a member."""

    session.delete(member)
    session.commit()

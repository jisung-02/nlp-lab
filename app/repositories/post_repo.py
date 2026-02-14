"""Database access helpers for posts."""

from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, col, select

from app.models.post import Post


def list_posts(session: Session) -> Sequence[Post]:
    """Return all posts sorted for admin listing."""

    return session.exec(
        select(Post).order_by(col(Post.created_at).desc(), col(Post.id).desc())
    ).all()


def get_post_by_id(session: Session, post_id: int) -> Post | None:
    """Return post by primary key."""

    return session.get(Post, post_id)


def get_post_by_slug(session: Session, slug: str) -> Post | None:
    """Return post by unique slug."""

    return session.exec(select(Post).where(col(Post.slug) == slug)).first()


def create_post(session: Session, post: Post) -> Post:
    """Persist a new post."""

    session.add(post)
    session.commit()
    session.refresh(post)
    return post


def update_post(session: Session, post: Post) -> Post:
    """Persist an updated post."""

    session.add(post)
    session.commit()
    session.refresh(post)
    return post


def delete_post(session: Session, post: Post) -> None:
    """Hard-delete a post."""

    session.delete(post)
    session.commit()

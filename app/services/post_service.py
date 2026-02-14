"""Post domain services."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError
from sqlmodel import Session

from app.models.post import Post
from app.repositories import post_repo
from app.schemas.post import PostCreateInput, PostUpdateInput


def parse_post_create_input(
    *,
    title: str,
    slug: str,
    content: str,
    is_published: str,
) -> PostCreateInput | None:
    """Return validated create payload or ``None``."""

    try:
        return PostCreateInput.model_validate(
            {
                "title": title,
                "slug": slug,
                "content": content,
                "is_published": is_published,
            }
        )
    except ValidationError:
        return None


def parse_post_update_input(
    *,
    title: str,
    slug: str,
    content: str,
    is_published: str,
) -> PostUpdateInput | None:
    """Return validated update payload or ``None``."""

    try:
        return PostUpdateInput.model_validate(
            {
                "title": title,
                "slug": slug,
                "content": content,
                "is_published": is_published,
            }
        )
    except ValidationError:
        return None


def list_posts(session: Session) -> Sequence[Post]:
    """Return posts for admin listing."""

    return post_repo.list_posts(session)


def create_post(session: Session, input_data: PostCreateInput) -> tuple[Post | None, str | None]:
    """Create a post or return an error message."""

    if post_repo.get_post_by_slug(session, input_data.slug) is not None:
        return None, "이미 사용 중인 slug입니다."

    post = Post(
        title=input_data.title,
        slug=input_data.slug,
        content=input_data.content,
        is_published=input_data.is_published,
    )
    return post_repo.create_post(session, post), None


def update_post(
    session: Session,
    post_id: int,
    input_data: PostUpdateInput,
) -> tuple[Post | None, str | None]:
    """Update a post or return an error message."""

    post = post_repo.get_post_by_id(session, post_id)
    if post is None:
        return None, "게시글을 찾을 수 없습니다."

    duplicate_post = post_repo.get_post_by_slug(session, input_data.slug)
    if duplicate_post is not None and duplicate_post.id != post.id:
        return None, "이미 사용 중인 slug입니다."

    post.title = input_data.title
    post.slug = input_data.slug
    post.content = input_data.content
    post.is_published = input_data.is_published

    return post_repo.update_post(session, post), None


def delete_post(session: Session, post_id: int) -> str | None:
    """Delete a post or return an error message."""

    post = post_repo.get_post_by_id(session, post_id)
    if post is None:
        return "게시글을 찾을 수 없습니다."

    post_repo.delete_post(session, post)
    return None

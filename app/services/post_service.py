"""Post domain services."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from app.core.constants import HOME_HERO_IMAGE_POST_SLUG
from app.models.post import Post
from app.repositories import post_repo
from app.schemas.post import PostCreateInput, PostUpdateInput

_HOME_HERO_HTTP_SCHEMES = ("http://", "https://")
_HOME_HERO_LEGACY_FALLBACK_URL = "/static/images/hero.jpg"
_HOME_HERO_DEFAULT_URL = "/static/images/hero/hero.jpg"


def parse_post_create_input(
    *,
    title: str,
    slug: str,
    content: str,
    is_published: str,
) -> PostCreateInput | None:
    """Return validated create payload or ``None``."""

    return _parse_post_input(
        PostCreateInput,
        title=title,
        slug=slug,
        content=content,
        is_published=is_published,
    )


def parse_post_update_input(
    *,
    title: str,
    slug: str,
    content: str,
    is_published: str,
) -> PostUpdateInput | None:
    """Return validated update payload or ``None``."""

    return _parse_post_input(
        PostUpdateInput,
        title=title,
        slug=slug,
        content=content,
        is_published=is_published,
    )


def _parse_post_input[TInputModel: BaseModel](
    model_class: type[TInputModel],
    *,
    title: str,
    slug: str,
    content: str,
    is_published: str,
) -> TInputModel | None:
    try:
        return model_class.model_validate(
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

    return [post for post in post_repo.list_posts(session) if not _is_home_hero_image_post(post)]


def get_home_hero_image_post(session: Session) -> Post | None:
    """Return the system post that stores home hero image URL."""

    return post_repo.get_post_by_slug(session, HOME_HERO_IMAGE_POST_SLUG)


def get_home_hero_image_urls(session: Session) -> list[str]:
    """Return hero image URLs from the system post payload."""

    hero_post = get_home_hero_image_post(session)
    if hero_post is None:
        return []

    return parse_home_hero_image_urls(hero_post.content)


def parse_home_hero_image_urls(raw_content: str | None) -> list[str]:
    """Parse hero image URLs from raw post content."""

    if raw_content is None:
        return []

    lines = [line.strip() for line in raw_content.splitlines()]
    if lines:
        normalized_urls = [_normalize_home_hero_image_url(line) for line in lines]
        return [url for url in normalized_urls if url is not None]

    single_line = _normalize_home_hero_image_url(raw_content.strip())
    if single_line is None:
        return []

    return [single_line]


def _normalize_home_hero_image_url(raw_url: str) -> str | None:
    """Normalize hero image URLs into local static paths."""

    url = raw_url.strip()
    if not url:
        return None

    lowered_url = url.lower()
    if lowered_url.startswith(_HOME_HERO_HTTP_SCHEMES):
        return None

    if url.startswith("/static/"):
        if url == _HOME_HERO_LEGACY_FALLBACK_URL:
            return _HOME_HERO_DEFAULT_URL
        return url

    if url.startswith("/images/"):
        return f"/static{url}"

    if url.startswith("/"):
        return f"/static{url}"

    if url.startswith("static/"):
        return f"/{url}"

    return f"/static/{url}"


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


def _is_home_hero_image_post(post: Post) -> bool:
    return post.slug == HOME_HERO_IMAGE_POST_SLUG

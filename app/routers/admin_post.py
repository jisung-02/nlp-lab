"""Admin post routes."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.core.constants import HOME_HERO_IMAGE_POST_SLUG, HOME_HERO_IMAGE_POST_TITLE
from app.db.session import get_session
from app.models.post import Post
from app.repositories import post_repo
from app.services import post_service
from app.services.auth_service import get_or_create_csrf_token, validate_or_raise_csrf

router = APIRouter(prefix="/admin/posts")

_ALLOWED_HERO_IMAGE_EXTENSIONS = {
    ".gif",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}
_UNSUPPORTED_HERO_IMAGE_SCHEMES = ("http://", "https://")
_MAX_HERO_IMAGE_BYTES = 8 * 1024 * 1024
_HERO_IMAGE_DIR = Path(__file__).resolve().parents[1] / "static" / "images" / "hero"
_HERO_IMAGE_WEB_PATH = "/static/images/hero"
_HERO_IMAGE_WEB_PREFIX = f"{_HERO_IMAGE_WEB_PATH}/"
_HERO_IMAGE_DEFAULT_URL = f"{_HERO_IMAGE_WEB_PATH}/hero.jpg"


@router.get("")
def posts_page(request: Request, session: Annotated[Session, Depends(get_session)]):
    return _render_posts_page(request, session)


@router.post("")
def create_post(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    title: Annotated[str, Form()],
    slug: Annotated[str, Form()],
    content: Annotated[str, Form()],
    hero_image_existing_urls: Annotated[list[str], Form(default_factory=list)],
    hero_image_filenames: Annotated[list[str], Form(default_factory=list)],
    hero_image_files: Annotated[list[UploadFile], File(default_factory=list)],
    hero_image_remove_urls: Annotated[list[str], Form(default_factory=list)],
    title_en: Annotated[str | None, Form()] = None,
    content_en: Annotated[str | None, Form()] = None,
    is_published: Annotated[str, Form()] = "true",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_or_raise_csrf(request, csrf_token)

    content_to_save = content
    if slug == HOME_HERO_IMAGE_POST_SLUG:
        content_for_hero, error_message = _resolve_home_hero_content(
            request=request,
            raw_content=content,
            hero_image_existing_urls=hero_image_existing_urls,
            hero_image_filenames=hero_image_filenames,
            hero_image_files=hero_image_files,
            hero_image_remove_urls=hero_image_remove_urls,
        )
        if error_message is not None:
            return _render_posts_page(
                request,
                session,
                error_message=error_message,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        content_to_save = content_for_hero

    create_input = post_service.parse_post_create_input(
        title=title,
        title_en=title_en,
        slug=slug,
        content=content_to_save,
        content_en=content_en,
        is_published=is_published,
    )
    if create_input is None:
        return _render_posts_page(
            request,
            session,
            error_message="게시글 입력값을 확인해주세요.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    _, error_message = post_service.create_post(session, create_input)
    if error_message is not None:
        return _render_posts_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/admin/posts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{id}/update")
def update_post(
    request: Request,
    id: int,
    session: Annotated[Session, Depends(get_session)],
    title: Annotated[str, Form()],
    slug: Annotated[str, Form()],
    content: Annotated[str, Form()],
    hero_image_existing_urls: Annotated[list[str], Form(default_factory=list)],
    hero_image_filenames: Annotated[list[str], Form(default_factory=list)],
    hero_image_files: Annotated[list[UploadFile], File(default_factory=list)],
    hero_image_remove_urls: Annotated[list[str], Form(default_factory=list)],
    title_en: Annotated[str | None, Form()] = None,
    content_en: Annotated[str | None, Form()] = None,
    is_published: Annotated[str, Form()] = "true",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_or_raise_csrf(request, csrf_token)

    content_to_save = content
    if slug == HOME_HERO_IMAGE_POST_SLUG:
        content_for_hero, error_message = _resolve_home_hero_content(
            request=request,
            raw_content=content,
            hero_image_existing_urls=hero_image_existing_urls,
            hero_image_filenames=hero_image_filenames,
            hero_image_files=hero_image_files,
            hero_image_remove_urls=hero_image_remove_urls,
        )
        if error_message is not None:
            return _render_posts_page(
                request,
                session,
                error_message=error_message,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        content_to_save = content_for_hero

    update_input = post_service.parse_post_update_input(
        title=title,
        title_en=title_en,
        slug=slug,
        content=content_to_save,
        content_en=content_en,
        is_published=is_published,
    )
    if update_input is None:
        return _render_posts_page(
            request,
            session,
            error_message="게시글 입력값을 확인해주세요.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    _, error_message = post_service.update_post(session, id, update_input)
    if error_message is not None:
        return _render_posts_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/admin/posts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{id}/delete")
def delete_post(
    request: Request,
    id: int,
    session: Annotated[Session, Depends(get_session)],
    csrf_token: Annotated[str, Form()] = "",
):
    validate_or_raise_csrf(request, csrf_token)

    error_message = post_service.delete_post(session, id)
    if error_message is not None:
        return _render_posts_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return RedirectResponse(url="/admin/posts", status_code=status.HTTP_303_SEE_OTHER)


def _render_posts_page(
    request: Request,
    session: Session,
    *,
    error_message: str | None = None,
    status_code: int = status.HTTP_200_OK,
):
    csrf_token = get_or_create_csrf_token(request)
    templates = cast(Jinja2Templates, request.app.state.templates)
    hero_image_post = post_service.get_home_hero_image_post(session)
    default_hero_image_url = request.url_for("static", path="images/hero/hero.jpg").path
    hero_image_urls = post_service.parse_home_hero_image_urls(
        hero_image_post.content if hero_image_post is not None else None
    )
    display_hero_image_urls = _sync_missing_home_hero_image_urls(
        session=session,
        hero_image_post=hero_image_post,
        hero_image_urls=hero_image_urls,
        default_hero_image_url=default_hero_image_url,
    )
    if not display_hero_image_urls:
        display_hero_image_urls = [default_hero_image_url]
    hero_image_edit_items = _build_hero_image_edit_items(display_hero_image_urls)
    hero_image_url = display_hero_image_urls[0]
    hero_image_content = "\n".join(display_hero_image_urls)
    return templates.TemplateResponse(
        request,
        "admin/posts.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error_message": error_message,
            "posts": post_service.list_posts(session),
            "hero_image_post": hero_image_post,
            "hero_image_urls": display_hero_image_urls,
            "hero_image_edit_items": hero_image_edit_items,
            "hero_image_url": hero_image_url,
            "hero_image_content": hero_image_content,
            "hero_image_default_url": default_hero_image_url,
            "home_hero_image_slug": HOME_HERO_IMAGE_POST_SLUG,
            "home_hero_image_title": HOME_HERO_IMAGE_POST_TITLE,
        },
        status_code=status_code,
    )


def _resolve_home_hero_content(
    *,
    request: Request,
    raw_content: str,
    hero_image_existing_urls: Sequence[str],
    hero_image_filenames: Sequence[str],
    hero_image_files: Sequence[UploadFile],
    hero_image_remove_urls: Sequence[str],
) -> tuple[str, str | None]:
    default_hero_image_url = request.url_for("static", path="images/hero/hero.jpg").path
    raw_lines = [line.strip() for line in raw_content.splitlines() if line.strip()]
    if raw_content and not raw_lines and raw_content.strip():
        raw_lines = [raw_content.strip()]
    if any(line.lower().startswith(_UNSUPPORTED_HERO_IMAGE_SCHEMES) for line in raw_lines):
        return (
            "",
            "이미지 경로는 http(s) 주소가 아닌 /static 기반 경로 또는 업로드 파일을 사용하세요.",
        )

    raw_urls = post_service.parse_home_hero_image_urls(raw_content)
    raw_urls, rename_map, rename_error = _rename_hero_images(
        raw_urls, hero_image_existing_urls, hero_image_filenames
    )
    if rename_error is not None:
        return "", rename_error
    raw_urls = _remove_hero_image_urls(raw_urls, hero_image_remove_urls, rename_map)

    removed_urls_for_cleanup = _collect_removed_urls_for_cleanup(
        hero_image_remove_urls=hero_image_remove_urls,
        rename_map=rename_map,
    )
    _delete_hero_image_files(removed_urls_for_cleanup)

    hero_image_files_to_save = list(hero_image_files)

    uploaded_urls, upload_error = _save_hero_image_files(hero_image_files_to_save)
    if upload_error is not None:
        return "", upload_error

    merged_urls = [*raw_urls, *uploaded_urls]
    if not merged_urls:
        return default_hero_image_url, None

    return "\n".join(merged_urls), None


def _sync_missing_home_hero_image_urls(
    *,
    session: Session,
    hero_image_post: Post | None,
    hero_image_urls: list[str],
    default_hero_image_url: str,
) -> list[str]:
    if hero_image_post is None:
        return hero_image_urls

    if not hero_image_urls:
        hero_image_post.content = default_hero_image_url
        post_repo.update_post(session, hero_image_post)
        return [default_hero_image_url]

    valid_urls = [
        _HERO_IMAGE_DEFAULT_URL if _is_default_hero_image_url(hero_image_url) else hero_image_url
        for hero_image_url in hero_image_urls
        if _is_default_hero_image_url(hero_image_url) or _hero_image_file_exists(hero_image_url)
    ]
    if valid_urls == hero_image_urls:
        if hero_image_post.content == _join_hero_image_urls(valid_urls):
            return valid_urls
        hero_image_post.content = _join_hero_image_urls(valid_urls)
        post_repo.update_post(session, hero_image_post)
        return valid_urls

    if valid_urls:
        hero_image_post.content = _join_hero_image_urls(valid_urls)
    else:
        valid_urls = [default_hero_image_url]
        hero_image_post.content = default_hero_image_url

    post_repo.update_post(session, hero_image_post)
    return valid_urls


def _join_hero_image_urls(urls: list[str]) -> str:
    return "\n".join(urls)


def _build_hero_image_edit_items(
    hero_image_urls: Sequence[str],
) -> list[dict[str, str | bool]]:
    items: list[dict[str, str | bool]] = []

    for hero_image_url in hero_image_urls:
        if not hero_image_url.startswith(_HERO_IMAGE_WEB_PREFIX):
            continue

        filename = hero_image_url.removeprefix(_HERO_IMAGE_WEB_PREFIX)
        if not filename:
            continue
        is_default_image = _is_default_hero_image_url(hero_image_url)
        items.append(
            {
                "url": hero_image_url,
                "filename": filename,
                "can_rename": not is_default_image,
                "can_remove": not is_default_image,
            }
        )

    return items


def _save_hero_image_files(
    hero_image_files: Sequence[UploadFile],
) -> tuple[list[str], str | None]:
    if not hero_image_files:
        return [], None

    _HERO_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []

    try:
        saved_urls = []
        for hero_image_file in hero_image_files:
            if hero_image_file.filename is None:
                _cleanup_hero_image_files(saved_paths)
                return [], "이미지 파일명을 확인해주세요."

            file_ext = Path(hero_image_file.filename).suffix.lower()
            if file_ext not in _ALLOWED_HERO_IMAGE_EXTENSIONS:
                _cleanup_hero_image_files(saved_paths)
                return [], "JPG, JPEG, PNG, WebP, GIF 형식의 이미지만 허용합니다."

            content = hero_image_file.file.read()
            if len(content) == 0:
                _cleanup_hero_image_files(saved_paths)
                return [], "빈 이미지 파일은 업로드할 수 없습니다."
            if len(content) > _MAX_HERO_IMAGE_BYTES:
                _cleanup_hero_image_files(saved_paths)
                return [], "이미지 파일 용량은 8MB를 초과할 수 없습니다."

            file_name = _make_unique_hero_image_filename(hero_image_file.filename)
            target_path = _HERO_IMAGE_DIR / file_name
            target_path.write_bytes(content)
            saved_paths.append(target_path)
            saved_urls.append(f"{_HERO_IMAGE_WEB_PATH}/{file_name}")

        return saved_urls, None
    except OSError:
        _cleanup_hero_image_files(saved_paths)
        return [], "이미지 업로드 중 오류가 발생했습니다. 다시 시도해주세요."


def _cleanup_hero_image_files(uploaded_files: Sequence[Path]) -> None:
    for path in uploaded_files:
        try:
            path.unlink()
        except OSError:
            pass


def _make_unique_hero_image_filename(uploaded_filename: str) -> str:
    """Generate a unique filename based on the uploaded original name."""

    filename = Path(uploaded_filename).name
    stem = filename.removesuffix(Path(filename).suffix)
    extension = Path(filename).suffix.lower()
    safe_stem = _sanitize_hero_image_stem(stem)

    file_name = f"{safe_stem[:80]}{extension}"
    target_path = _HERO_IMAGE_DIR / file_name
    if not target_path.exists():
        return file_name

    return f"{safe_stem[:80]}-{uuid4().hex}{extension}"


def _rename_hero_images(
    image_urls: list[str],
    hero_image_existing_urls: Sequence[str],
    hero_image_filenames: Sequence[str],
) -> tuple[list[str], dict[str, str], str | None]:
    if not hero_image_existing_urls or not hero_image_filenames:
        return image_urls, {}, None

    rename_requests = dict(
        (old_url.strip(), new_name.strip())
        for old_url, new_name in zip(hero_image_existing_urls, hero_image_filenames, strict=False)
        if old_url.strip() and new_name.strip()
    )
    if not rename_requests:
        return image_urls, {}, None

    renamed_urls = list(image_urls)
    rename_map: dict[str, str] = {}

    for old_url, new_name in rename_requests.items():
        if old_url not in image_urls:
            continue
        if _is_default_hero_image_url(old_url):
            return [], {}, "기본 히어로 이미지는 이름을 변경할 수 없습니다."
        if not _is_hero_image_file_url(old_url):
            return [], {}, "잘못된 히어로 이미지 경로입니다."

        new_url, error = _rename_hero_image_file(old_url, new_name)
        if error is not None:
            return [], {}, error
        rename_map[old_url] = new_url

    if rename_map:
        renamed_urls = [rename_map.get(url, url) for url in image_urls]

    return renamed_urls, rename_map, None


def _normalize_hero_image_urls_for_admin(
    hero_image_urls: Sequence[str],
) -> set[str]:
    return set(post_service.parse_home_hero_image_urls("\n".join(hero_image_urls)))


def _collect_removable_hero_image_urls(
    hero_image_urls: Sequence[str],
) -> set[str]:
    return {
        hero_image_url
        for hero_image_url in _normalize_hero_image_urls_for_admin(hero_image_urls)
        if _is_removable_hero_image_url(hero_image_url)
    }


def _collect_removed_urls_for_cleanup(
    *,
    hero_image_remove_urls: Sequence[str],
    rename_map: dict[str, str],
) -> list[str]:
    removed_urls = _collect_removable_hero_image_urls(hero_image_remove_urls)
    for old_url, new_url in rename_map.items():
        if old_url in removed_urls:
            removed_urls.add(new_url)
    return list(removed_urls)


def _remove_hero_image_urls(
    hero_image_urls: list[str],
    hero_image_remove_urls: Sequence[str],
    rename_map: dict[str, str],
) -> list[str]:
    removed_urls = _collect_removed_urls_for_cleanup(
        hero_image_remove_urls=hero_image_remove_urls,
        rename_map=rename_map,
    )

    if not removed_urls:
        return hero_image_urls

    return [url for url in hero_image_urls if url not in removed_urls]


def _delete_hero_image_files(hero_image_urls: Sequence[str]) -> None:
    for hero_image_url in hero_image_urls:
        if not _is_removable_hero_image_url(hero_image_url):
            continue

        file_name = hero_image_url.removeprefix(_HERO_IMAGE_WEB_PREFIX)
        if not file_name or Path(file_name).name != file_name:
            continue

        target_path = _HERO_IMAGE_DIR / file_name
        if target_path.is_file():
            try:
                target_path.unlink()
            except OSError:
                pass


def _is_removable_hero_image_url(hero_image_url: str) -> bool:
    if _is_default_hero_image_url(hero_image_url):
        return False

    return _is_hero_image_file_url(hero_image_url)


def _is_hero_image_file_url(hero_image_url: str) -> bool:
    if not hero_image_url.startswith(_HERO_IMAGE_WEB_PREFIX):
        return False

    file_name = hero_image_url.removeprefix(_HERO_IMAGE_WEB_PREFIX)
    return bool(file_name) and Path(file_name).name == file_name


def _rename_hero_image_file(old_url: str, new_name: str) -> tuple[str, str | None]:
    if not old_url.startswith(_HERO_IMAGE_WEB_PREFIX):
        return "", "히어로 이미지는 hero 폴더 경로에서만 파일명을 변경할 수 있습니다."

    old_path = _HERO_IMAGE_DIR / old_url.removeprefix(_HERO_IMAGE_WEB_PREFIX)
    if not old_path.exists():
        return "", "기존 히어로 이미지를 찾을 수 없습니다."

    requested_filename = Path(new_name).name
    if not requested_filename:
        return "", "변경할 이미지 파일명을 입력해주세요."

    extension = Path(requested_filename).suffix.lower()
    if extension == "":
        extension = old_path.suffix.lower()

    if extension not in _ALLOWED_HERO_IMAGE_EXTENSIONS:
        return "", "이미지 확장자는 jpg, jpeg, png, webp, gif만 허용합니다."

    requested_stem = Path(requested_filename).stem
    safe_stem = _sanitize_hero_image_stem(requested_stem, fallback=old_path.stem)

    target_filename = f"{safe_stem[:80]}{extension}"
    target_path = _HERO_IMAGE_DIR / target_filename
    if target_path.exists() and target_path != old_path:
        target_filename = f"{safe_stem[:80]}-{uuid4().hex}{extension}"
        target_path = _HERO_IMAGE_DIR / target_filename

    try:
        old_path.replace(target_path)
    except OSError:
        return "", "이미지 이름 변경 중 오류가 발생했습니다. 다시 시도해주세요."

    return f"{_HERO_IMAGE_WEB_PATH}/{target_filename}", None


def _hero_image_file_exists(hero_image_url: str) -> bool:
    if _is_default_hero_image_url(hero_image_url):
        return True

    if not hero_image_url.startswith(_HERO_IMAGE_WEB_PREFIX):
        return True

    file_name = hero_image_url.removeprefix(_HERO_IMAGE_WEB_PREFIX)
    if not file_name:
        return False

    safe_file_name = Path(file_name).name
    if safe_file_name != file_name:
        return False

    return (_HERO_IMAGE_DIR / safe_file_name).exists()


def _is_default_hero_image_url(hero_image_url: str) -> bool:
    return hero_image_url in (_HERO_IMAGE_DEFAULT_URL, "/static/images/hero.jpg")


def _sanitize_hero_image_stem(raw_stem: str, *, fallback: str = "hero-image") -> str:
    sanitized_stem = re.sub(r"[^a-zA-Z0-9가-힣._-]", "-", raw_stem).strip("-")
    if sanitized_stem:
        return sanitized_stem

    sanitized_fallback = re.sub(r"[^a-zA-Z0-9가-힣._-]", "-", fallback).strip("-")
    if sanitized_fallback:
        return sanitized_fallback

    return "hero-image"

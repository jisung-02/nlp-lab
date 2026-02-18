"""Admin member routes."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from starlette.datastructures import UploadFile

from app.core.constants import MemberRole
from app.db.session import get_session
from app.services import member_service
from app.services.auth_service import get_or_create_csrf_token, validate_or_raise_csrf

router = APIRouter(prefix="/admin/members")

_ALLOWED_MEMBER_PHOTO_EXTENSIONS = {
    ".gif",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}
_MAX_MEMBER_PHOTO_BYTES = 8 * 1024 * 1024
_MEMBER_PHOTO_DIR = Path(__file__).resolve().parents[1] / "static" / "images" / "members"
_MEMBER_PHOTO_WEB_PATH = "/static/images/members"


@router.get("")
def members_page(request: Request, session: Annotated[Session, Depends(get_session)]):
    return _render_members_page(request, session)


@router.post("")
async def create_member(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    email: Annotated[str, Form()],
    name_en: Annotated[str | None, Form()] = None,
    photo_url: Annotated[str | None, Form()] = None,
    bio: Annotated[str | None, Form()] = None,
    bio_en: Annotated[str | None, Form()] = None,
    display_order: Annotated[str, Form()] = "100",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_or_raise_csrf(request, csrf_token)

    photo_file = _extract_member_photo_file(await request.form())
    resolved_photo_url, upload_error = _resolve_member_photo_url(
        photo_url=photo_url,
        photo_file=photo_file,
    )
    if upload_error is not None:
        return _render_members_page(
            request,
            session,
            error_message=upload_error,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    create_input = member_service.parse_member_create_input(
        name=name,
        name_en=name_en,
        role=role,
        email=email,
        photo_url=resolved_photo_url,
        bio=bio,
        bio_en=bio_en,
        display_order=display_order,
    )
    if create_input is None:
        return _render_members_page(
            request,
            session,
            error_message="멤버 입력값을 확인해주세요.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    _, error_message = member_service.create_member(session, create_input)
    if error_message is not None:
        return _render_members_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/admin/members", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{id}/update")
async def update_member(
    request: Request,
    id: int,
    session: Annotated[Session, Depends(get_session)],
    name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    email: Annotated[str, Form()],
    name_en: Annotated[str | None, Form()] = None,
    photo_url: Annotated[str | None, Form()] = None,
    bio: Annotated[str | None, Form()] = None,
    bio_en: Annotated[str | None, Form()] = None,
    display_order: Annotated[str, Form()] = "100",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_or_raise_csrf(request, csrf_token)

    photo_file = _extract_member_photo_file(await request.form())
    resolved_photo_url, upload_error = _resolve_member_photo_url(
        photo_url=photo_url,
        photo_file=photo_file,
    )
    if upload_error is not None:
        return _render_members_page(
            request,
            session,
            error_message=upload_error,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    update_input = member_service.parse_member_update_input(
        name=name,
        name_en=name_en,
        role=role,
        email=email,
        photo_url=resolved_photo_url,
        bio=bio,
        bio_en=bio_en,
        display_order=display_order,
    )
    if update_input is None:
        return _render_members_page(
            request,
            session,
            error_message="멤버 입력값을 확인해주세요.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    _, error_message = member_service.update_member(session, id, update_input)
    if error_message is not None:
        return _render_members_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/admin/members", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{id}/delete")
def delete_member(
    request: Request,
    id: int,
    session: Annotated[Session, Depends(get_session)],
    csrf_token: Annotated[str, Form()] = "",
):
    validate_or_raise_csrf(request, csrf_token)

    error_message = member_service.delete_member(session, id)
    if error_message is not None:
        return _render_members_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return RedirectResponse(url="/admin/members", status_code=status.HTTP_303_SEE_OTHER)


def _render_members_page(
    request: Request,
    session: Session,
    *,
    error_message: str | None = None,
    status_code: int = status.HTTP_200_OK,
):
    csrf_token = get_or_create_csrf_token(request)
    templates = cast(Jinja2Templates, request.app.state.templates)
    return templates.TemplateResponse(
        request,
        "admin/members.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error_message": error_message,
            "members": member_service.list_members(session),
            "roles": list(MemberRole),
        },
        status_code=status_code,
    )


def _extract_member_photo_file(form_data: Mapping[str, object]) -> UploadFile | None:
    uploaded_file = form_data.get("photo_file")
    if not isinstance(uploaded_file, UploadFile):
        return None
    if uploaded_file.filename is None or not uploaded_file.filename.strip():
        return None
    return uploaded_file


def _resolve_member_photo_url(
    *,
    photo_url: str | None,
    photo_file: UploadFile | None,
) -> tuple[str | None, str | None]:
    normalized_photo_url = photo_url.strip() if isinstance(photo_url, str) else None
    if normalized_photo_url == "":
        normalized_photo_url = None

    if photo_file is None:
        return normalized_photo_url, None

    uploaded_photo_url, error_message = _save_member_photo_file(photo_file)
    if error_message is not None:
        return None, error_message
    return uploaded_photo_url, None


def _save_member_photo_file(photo_file: UploadFile) -> tuple[str | None, str | None]:
    if photo_file.filename is None or not photo_file.filename.strip():
        return None, "사진 파일명을 확인해주세요."

    file_ext = Path(photo_file.filename).suffix.lower()
    if file_ext not in _ALLOWED_MEMBER_PHOTO_EXTENSIONS:
        return None, "JPG, JPEG, PNG, WebP, GIF 형식의 이미지만 허용합니다."

    content = photo_file.file.read()
    if len(content) == 0:
        return None, "빈 이미지 파일은 업로드할 수 없습니다."
    if len(content) > _MAX_MEMBER_PHOTO_BYTES:
        return None, "이미지 파일 용량은 8MB를 초과할 수 없습니다."

    _MEMBER_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    file_name = _make_unique_member_photo_filename(photo_file.filename)
    target_path = _MEMBER_PHOTO_DIR / file_name
    try:
        target_path.write_bytes(content)
    except OSError:
        return None, "사진 업로드 중 오류가 발생했습니다. 다시 시도해주세요."

    return f"{_MEMBER_PHOTO_WEB_PATH}/{file_name}", None


def _make_unique_member_photo_filename(uploaded_filename: str) -> str:
    filename = Path(uploaded_filename).name
    stem = filename.removesuffix(Path(filename).suffix)
    extension = Path(filename).suffix.lower()
    safe_stem = _sanitize_member_photo_stem(stem)

    file_name = f"{safe_stem[:80]}{extension}"
    target_path = _MEMBER_PHOTO_DIR / file_name
    if not target_path.exists():
        return file_name

    return f"{safe_stem[:80]}-{uuid4().hex}{extension}"


def _sanitize_member_photo_stem(raw_stem: str, *, fallback: str = "member-photo") -> str:
    sanitized_stem = re.sub(r"[^a-zA-Z0-9가-힣._-]", "-", raw_stem).strip("-")
    if sanitized_stem:
        return sanitized_stem

    sanitized_fallback = re.sub(r"[^a-zA-Z0-9가-힣._-]", "-", fallback).strip("-")
    if sanitized_fallback:
        return sanitized_fallback

    return "member-photo"

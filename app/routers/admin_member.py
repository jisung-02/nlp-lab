"""Admin member routes."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.core.constants import MemberRole
from app.db.session import get_session
from app.services import member_service
from app.services.auth_service import get_or_create_csrf_token, validate_or_raise_csrf

router = APIRouter(prefix="/admin/members")


@router.get("")
def members_page(request: Request, session: Annotated[Session, Depends(get_session)]):
    return _render_members_page(request, session)


@router.post("")
def create_member(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    email: Annotated[str, Form()],
    photo_url: Annotated[str | None, Form()] = None,
    bio: Annotated[str | None, Form()] = None,
    display_order: Annotated[str, Form()] = "100",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_or_raise_csrf(request, csrf_token)

    create_input = member_service.parse_member_create_input(
        name=name,
        role=role,
        email=email,
        photo_url=photo_url,
        bio=bio,
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
def update_member(
    request: Request,
    id: int,
    session: Annotated[Session, Depends(get_session)],
    name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    email: Annotated[str, Form()],
    photo_url: Annotated[str | None, Form()] = None,
    bio: Annotated[str | None, Form()] = None,
    display_order: Annotated[str, Form()] = "100",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_or_raise_csrf(request, csrf_token)

    update_input = member_service.parse_member_update_input(
        name=name,
        role=role,
        email=email,
        photo_url=photo_url,
        bio=bio,
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

"""Admin post routes."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.db.session import get_session
from app.services import post_service
from app.services.auth_service import get_or_create_csrf_token, validate_csrf_token

router = APIRouter(prefix="/admin/posts")


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
    is_published: Annotated[str, Form()] = "true",
    csrf_token: Annotated[str, Form()] = "",
):
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    create_input = post_service.parse_post_create_input(
        title=title,
        slug=slug,
        content=content,
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
    is_published: Annotated[str, Form()] = "true",
    csrf_token: Annotated[str, Form()] = "",
):
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    update_input = post_service.parse_post_update_input(
        title=title,
        slug=slug,
        content=content,
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
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

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
    return templates.TemplateResponse(
        request,
        "admin/posts.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error_message": error_message,
            "posts": post_service.list_posts(session),
        },
        status_code=status_code,
    )

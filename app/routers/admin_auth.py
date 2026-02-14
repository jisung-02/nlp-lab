"""Admin authentication routes."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.member import Member
from app.models.post import Post
from app.models.project import Project
from app.models.publication import Publication
from app.services.auth_service import (
    authenticate_admin,
    get_authenticated_admin,
    get_or_create_csrf_token,
    login_admin,
    logout_admin,
    parse_login_input,
    validate_csrf_token,
)

router = APIRouter(prefix="/admin")


def _templates(request: Request) -> Jinja2Templates:
    return cast(Jinja2Templates, request.app.state.templates)


def _render_login_page(request: Request, error_message: str | None = None, status_code: int = 200):
    csrf_token = get_or_create_csrf_token(request)
    return _templates(request).TemplateResponse(
        request,
        "admin/login.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error_message": error_message,
        },
        status_code=status_code,
    )


@router.get("/login")
def login_page(request: Request, session: Annotated[Session, Depends(get_session)]):
    admin_user = get_authenticated_admin(request, session)
    if admin_user is not None:
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    return _render_login_page(request)


@router.post("/login")
def login(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
):
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    login_input = parse_login_input(username=username, password=password, csrf_token=csrf_token)
    if login_input is None:
        return _render_login_page(
            request,
            error_message="입력값을 확인해주세요.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    admin_user = authenticate_admin(
        session,
        username=login_input.username,
        password=login_input.password,
    )
    if admin_user is None:
        return _render_login_page(
            request,
            error_message="아이디 또는 비밀번호가 올바르지 않습니다.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    login_admin(request, admin_user)
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout(request: Request, csrf_token: Annotated[str, Form()]):
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    logout_admin(request)
    return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("")
def dashboard(request: Request, session: Annotated[Session, Depends(get_session)]):
    csrf_token = get_or_create_csrf_token(request)
    member_count = len(session.exec(select(Member.id)).all())
    project_count = len(session.exec(select(Project.id)).all())
    publication_count = len(session.exec(select(Publication.id)).all())
    post_count = len(session.exec(select(Post.id)).all())
    return _templates(request).TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "member_count": member_count,
            "project_count": project_count,
            "publication_count": publication_count,
            "post_count": post_count,
        },
    )

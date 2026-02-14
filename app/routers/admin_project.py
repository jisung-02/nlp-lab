"""Admin project routes."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.core.constants import ProjectStatus
from app.db.session import get_session
from app.services import project_service
from app.services.auth_service import get_or_create_csrf_token, validate_csrf_token

router = APIRouter(prefix="/admin/projects")


@router.get("")
def projects_page(request: Request, session: Annotated[Session, Depends(get_session)]):
    return _render_projects_page(request, session)


@router.post("")
def create_project(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    title: Annotated[str, Form()],
    slug: Annotated[str, Form()],
    summary: Annotated[str, Form()],
    description: Annotated[str, Form()],
    status_value: Annotated[str, Form(alias="status")],
    start_date: Annotated[str, Form()],
    end_date: Annotated[str | None, Form()] = None,
    csrf_token: Annotated[str, Form()] = "",
):
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    create_input = project_service.parse_project_create_input(
        title=title,
        slug=slug,
        summary=summary,
        description=description,
        status=status_value,
        start_date=start_date,
        end_date=end_date,
    )
    if create_input is None:
        return _render_projects_page(
            request,
            session,
            error_message="프로젝트 입력값을 확인해주세요.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    _, error_message = project_service.create_project(session, create_input)
    if error_message is not None:
        return _render_projects_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/admin/projects", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{id}/update")
def update_project(
    request: Request,
    id: int,
    session: Annotated[Session, Depends(get_session)],
    title: Annotated[str, Form()],
    slug: Annotated[str, Form()],
    summary: Annotated[str, Form()],
    description: Annotated[str, Form()],
    status_value: Annotated[str, Form(alias="status")],
    start_date: Annotated[str, Form()],
    end_date: Annotated[str | None, Form()] = None,
    csrf_token: Annotated[str, Form()] = "",
):
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    update_input = project_service.parse_project_update_input(
        title=title,
        slug=slug,
        summary=summary,
        description=description,
        status=status_value,
        start_date=start_date,
        end_date=end_date,
    )
    if update_input is None:
        return _render_projects_page(
            request,
            session,
            error_message="프로젝트 입력값을 확인해주세요.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    _, error_message = project_service.update_project(session, id, update_input)
    if error_message is not None:
        return _render_projects_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/admin/projects", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{id}/delete")
def delete_project(
    request: Request,
    id: int,
    session: Annotated[Session, Depends(get_session)],
    csrf_token: Annotated[str, Form()] = "",
):
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    error_message = project_service.delete_project(session, id)
    if error_message is not None:
        return _render_projects_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return RedirectResponse(url="/admin/projects", status_code=status.HTTP_303_SEE_OTHER)


def _render_projects_page(
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
        "admin/projects.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error_message": error_message,
            "projects": project_service.list_projects(session),
            "statuses": list(ProjectStatus),
        },
        status_code=status_code,
    )

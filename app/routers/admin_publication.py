"""Admin publication routes."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.db.session import get_session
from app.services import publication_service
from app.services.auth_service import get_or_create_csrf_token, validate_csrf_token

router = APIRouter(prefix="/admin/publications")


@router.get("")
def publications_page(request: Request, session: Annotated[Session, Depends(get_session)]):
    return _render_publications_page(request, session)


@router.post("")
def create_publication(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    title: Annotated[str, Form()],
    authors: Annotated[str, Form()],
    venue: Annotated[str, Form()],
    year: Annotated[str, Form()],
    link: Annotated[str | None, Form()] = None,
    related_project_id: Annotated[str | None, Form()] = None,
    csrf_token: Annotated[str, Form()] = "",
):
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    create_input = publication_service.parse_publication_create_input(
        title=title,
        authors=authors,
        venue=venue,
        year=year,
        link=link,
        related_project_id=related_project_id,
    )
    if create_input is None:
        return _render_publications_page(
            request,
            session,
            error_message="논문 입력값을 확인해주세요.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    _, error_message = publication_service.create_publication(session, create_input)
    if error_message is not None:
        return _render_publications_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/admin/publications", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{id}/update")
def update_publication(
    request: Request,
    id: int,
    session: Annotated[Session, Depends(get_session)],
    title: Annotated[str, Form()],
    authors: Annotated[str, Form()],
    venue: Annotated[str, Form()],
    year: Annotated[str, Form()],
    link: Annotated[str | None, Form()] = None,
    related_project_id: Annotated[str | None, Form()] = None,
    csrf_token: Annotated[str, Form()] = "",
):
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    update_input = publication_service.parse_publication_update_input(
        title=title,
        authors=authors,
        venue=venue,
        year=year,
        link=link,
        related_project_id=related_project_id,
    )
    if update_input is None:
        return _render_publications_page(
            request,
            session,
            error_message="논문 입력값을 확인해주세요.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    _, error_message = publication_service.update_publication(session, id, update_input)
    if error_message is not None:
        return _render_publications_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/admin/publications", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{id}/delete")
def delete_publication(
    request: Request,
    id: int,
    session: Annotated[Session, Depends(get_session)],
    csrf_token: Annotated[str, Form()] = "",
):
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    error_message = publication_service.delete_publication(session, id)
    if error_message is not None:
        return _render_publications_page(
            request,
            session,
            error_message=error_message,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return RedirectResponse(url="/admin/publications", status_code=status.HTTP_303_SEE_OTHER)


def _render_publications_page(
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
        "admin/publications.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error_message": error_message,
            "publications": publication_service.list_publications(session),
            "projects": publication_service.list_projects_for_publications(session),
        },
        status_code=status_code,
    )

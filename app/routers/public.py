"""Public page routes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.constants import MemberRole, ProjectStatus
from app.db.session import get_session
from app.models.member import Member
from app.models.post import Post
from app.models.project import Project
from app.models.publication import Publication

router = APIRouter()


@router.get("/")
def home(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
):
    latest_projects = session.exec(
        select(Project).order_by(col(Project.created_at).desc()).limit(3)
    ).all()
    latest_publications = session.exec(
        select(Publication)
        .order_by(col(Publication.year).desc(), col(Publication.id).desc())
        .limit(5)
    ).all()
    latest_posts = session.exec(
        select(Post)
        .where(col(Post.is_published).is_(True))
        .order_by(col(Post.created_at).desc())
        .limit(3)
    ).all()
    templates = cast(Jinja2Templates, request.app.state.templates)
    return templates.TemplateResponse(
        request,
        "public/home.html",
        {
            "request": request,
            "projects": latest_projects,
            "publications": latest_publications,
            "posts": latest_posts,
        },
    )


@router.get("/members")
def members_page(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
):
    members = session.exec(
        select(Member).order_by(col(Member.display_order).asc(), col(Member.created_at).asc())
    ).all()
    templates = cast(Jinja2Templates, request.app.state.templates)
    return templates.TemplateResponse(
        request,
        "public/members.html",
        {
            "request": request,
            "grouped_members": _group_members_by_role(members),
        },
    )


@router.get("/projects")
def projects_page(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    status: Annotated[ProjectStatus | None, Query()] = None,
):
    stmt = select(Project)
    if status is not None:
        stmt = stmt.where(col(Project.status) == status)
    projects = session.exec(stmt.order_by(col(Project.created_at).desc())).all()
    templates = cast(Jinja2Templates, request.app.state.templates)
    return templates.TemplateResponse(
        request,
        "public/projects.html",
        {
            "request": request,
            "projects": projects,
            "selected_status": status.value if status else "all",
        },
    )


@router.get("/projects/{slug}")
def project_detail_page(
    request: Request,
    slug: str,
    session: Annotated[Session, Depends(get_session)],
):
    project = session.exec(select(Project).where(col(Project.slug) == slug)).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    related_publications = session.exec(
        select(Publication)
        .where(col(Publication.related_project_id) == project.id)
        .order_by(col(Publication.year).desc(), col(Publication.id).desc())
    ).all()

    templates = cast(Jinja2Templates, request.app.state.templates)
    return templates.TemplateResponse(
        request,
        "public/project_detail.html",
        {
            "request": request,
            "project": project,
            "publications": related_publications,
        },
    )


@router.get("/publications")
def publications_page(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    year: Annotated[int | None, Query(ge=1900, le=3000)] = None,
):
    stmt = select(Publication)
    if year is not None:
        stmt = stmt.where(col(Publication.year) == year)

    publications = session.exec(
        stmt.order_by(col(Publication.year).desc(), col(Publication.id).desc())
    ).all()
    years = session.exec(
        select(col(Publication.year)).distinct().order_by(col(Publication.year).desc())
    ).all()

    templates = cast(Jinja2Templates, request.app.state.templates)
    return templates.TemplateResponse(
        request,
        "public/publications.html",
        {
            "request": request,
            "publications": publications,
            "years": years,
            "selected_year": year,
        },
    )


@router.get("/contact")
def contact_page(request: Request):
    settings = get_settings()
    templates = cast(Jinja2Templates, request.app.state.templates)
    return templates.TemplateResponse(
        request,
        "public/contact.html",
        {
            "request": request,
            "contact_email": settings.contact_email,
            "contact_address": settings.contact_address,
            "contact_map_url": settings.contact_map_url,
        },
    )


def _group_members_by_role(members: Sequence[Member]) -> list[tuple[MemberRole, list[Member]]]:
    grouped: dict[MemberRole, list[Member]] = {role: [] for role in MemberRole}
    for member in members:
        grouped[member.role].append(member)
    return [(role, grouped[role]) for role in MemberRole if grouped[role]]

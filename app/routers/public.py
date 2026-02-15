"""Public page routes."""

from __future__ import annotations

from typing import Annotated, cast
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.constants import HOME_HERO_IMAGE_POST_SLUG, ProjectStatus
from app.db.session import get_session
from app.models.member import Member
from app.models.post import Post
from app.models.project import Project
from app.models.publication import Publication
from app.services import post_service

router = APIRouter()


@router.get("/")
def home(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
):
    default_hero_image_url = request.url_for("static", path="images/hero/hero.jpg").path
    hero_images = post_service.get_home_hero_image_urls(session)
    hero_image_urls = hero_images if hero_images else [default_hero_image_url]
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
        .where(col(Post.slug) != HOME_HERO_IMAGE_POST_SLUG)
        .order_by(col(Post.created_at).desc())
        .limit(3)
    ).all()
    featured_members = session.exec(
        select(Member)
        .order_by(col(Member.display_order).asc(), col(Member.created_at).asc())
        .limit(8)
    ).all()
    settings = get_settings()
    return _render_public_template(
        request,
        "public/home.html",
        _public_context(
            request,
            projects=latest_projects,
            publications=latest_publications,
            posts=latest_posts,
            members=featured_members,
            hero_images=hero_image_urls,
            hero_image_url=hero_image_urls[0],
            contact_email=settings.contact_email,
            contact_address=settings.contact_address,
        ),
    )


@router.get("/members")
def members_page(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
):
    members = session.exec(
        select(Member).order_by(col(Member.display_order).asc(), col(Member.created_at).asc())
    ).all()
    return _render_public_template(
        request,
        "public/members.html",
        _public_context(
            request,
            members=members,
        ),
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
    return _render_public_template(
        request,
        "public/projects.html",
        _public_context(
            request,
            projects=projects,
            selected_status=status.value if status else "all",
        ),
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

    return _render_public_template(
        request,
        "public/project_detail.html",
        _public_context(
            request,
            project=project,
            publications=related_publications,
        ),
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

    return _render_public_template(
        request,
        "public/publications.html",
        _public_context(
            request,
            publications=publications,
            years=years,
            selected_year=year,
        ),
    )


@router.get("/contact")
def contact_page(request: Request):
    settings = get_settings()
    return _render_public_template(
        request,
        "public/contact.html",
        _public_context(
            request,
            contact_email=settings.contact_email,
            contact_address=settings.contact_address,
            contact_map_url=settings.contact_map_url,
        ),
    )


SUPPORTED_PUBLIC_LANGS = {"kr", "en"}
DEFAULT_PUBLIC_LANG = "kr"
PUBLIC_LANG_COOKIE_NAME = "nlp_lang"


def _render_public_template(
    request: Request,
    template_name: str,
    context: dict[str, object],
):
    templates = cast(Jinja2Templates, request.app.state.templates)
    response = templates.TemplateResponse(request, template_name, context)
    response.set_cookie(
        key=PUBLIC_LANG_COOKIE_NAME,
        value=cast(str, context["lang"]),
        max_age=60 * 60 * 24 * 365,
        samesite="lax",
    )
    return response


def _public_context(request: Request, **extra_context: object) -> dict[str, object]:
    lang = _resolve_public_lang(request)
    context: dict[str, object] = {
        "request": request,
        "lang": lang,
        "is_en": lang == "en",
        "lang_kr_url": _replace_lang_in_query(request, "kr"),
        "lang_en_url": _replace_lang_in_query(request, "en"),
    }
    context.update(extra_context)
    return context


def _resolve_public_lang(request: Request) -> str:
    query_lang = request.query_params.get("lang", "").lower()
    if query_lang in SUPPORTED_PUBLIC_LANGS:
        return query_lang

    cookie_lang = request.cookies.get(PUBLIC_LANG_COOKIE_NAME, "").lower()
    if cookie_lang in SUPPORTED_PUBLIC_LANGS:
        return cookie_lang

    return DEFAULT_PUBLIC_LANG


def _replace_lang_in_query(request: Request, target_lang: str) -> str:
    query_params = dict(request.query_params)
    query_params["lang"] = target_lang
    encoded_query = urlencode(query_params)
    if not encoded_query:
        return request.url.path
    return f"{request.url.path}?{encoded_query}"

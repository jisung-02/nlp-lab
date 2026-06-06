"""Public page routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast
from urllib.parse import urlencode
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
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

PUBLIC_SEO_COPY = {
    "/": {
        "kr": (
            "경희대학교 NLP 연구실은 자연어처리, 언어 이해, 질의응답, 대화 시스템, "
            "정보검색을 연구합니다."
        ),
        "en": (
            "Kyung Hee University NLP Lab researches natural language processing, "
            "language understanding, question answering, dialogue systems, "
            "and information retrieval."
        ),
    },
    "/members": {
        "kr": "경희대학교 NLP 연구실 구성원과 연구진을 소개합니다.",
        "en": "Meet the members and researchers of Kyung Hee University NLP Lab.",
    },
    "/projects": {
        "kr": "경희대학교 NLP 연구실의 자연어처리 연구 분야와 프로젝트를 소개합니다.",
        "en": (
            "Explore natural language processing research areas and projects "
            "at Kyung Hee University NLP Lab."
        ),
    },
    "/publications": {
        "kr": "경희대학교 NLP 연구실의 논문과 연구 성과를 확인하세요.",
        "en": "Browse publications and research outputs from Kyung Hee University NLP Lab.",
    },
    "/contact": {
        "kr": "경희대학교 NLP 연구실 위치, 연락처, 방문 정보를 안내합니다.",
        "en": "Find contact, location, and visit information for Kyung Hee University NLP Lab.",
    },
}

PUBLIC_STATIC_SITEMAP_PATHS = ("/", "/members", "/projects", "/publications", "/contact")

LEGACY_PUBLIC_REDIRECTS = {
    "/index.html": "/",
    "/home": "/",
    "/people": "/members",
    "/Contact": "/contact",
    "/Members": "/members",
    "/Research_Overview": "/projects",
    "/research_1": "/projects",
    "/research_2": "/projects",
    "/papers_with_code": "/publications",
    "/Domestic_Journal": "/publications?category=domestic_journal",
    "/International_Journal": "/publications?category=international_journal",
    "/Domestic_Conference": "/publications?category=domestic_conference",
    "/International_Conference": "/publications?category=international_conference",
}


def _make_legacy_redirect_handler(target_url: str):
    def legacy_redirect():
        return RedirectResponse(url=target_url, status_code=301)

    return legacy_redirect


for legacy_path, target_url in LEGACY_PUBLIC_REDIRECTS.items():
    router.add_api_route(
        legacy_path,
        _make_legacy_redirect_handler(target_url),
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )


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
            project_statuses=list(ProjectStatus),
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


@router.get("/robots.txt", include_in_schema=False)
def robots_txt(request: Request):
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin",
            "",
            f"Sitemap: {_absolute_public_url(request, '/sitemap.xml')}",
            "",
        ]
    )
    return PlainTextResponse(content)


@router.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
def favicon(request: Request):
    return RedirectResponse(
        url=str(request.url_for("static", path="images/favicon.ico")),
        status_code=307,
    )


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
):
    projects = session.exec(select(Project).order_by(col(Project.updated_at).desc())).all()
    sitemap_entries: list[tuple[str, str | None]] = []

    for path in PUBLIC_STATIC_SITEMAP_PATHS:
        for lang in ("kr", "en"):
            sitemap_entries.append((_localized_path(path, lang), None))

    for project in projects:
        for lang in ("kr", "en"):
            sitemap_entries.append(
                (
                    _localized_path(f"/projects/{project.slug}", lang),
                    _format_sitemap_lastmod(project.updated_at),
                )
            )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, lastmod in sitemap_entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_escape(_absolute_public_url(request, path))}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")

    return Response("\n".join(lines), media_type="application/xml; charset=utf-8")


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
    settings = get_settings()
    context: dict[str, object] = {
        "request": request,
        "lang": lang,
        "is_en": lang == "en",
        "lang_kr_url": _replace_lang_in_query(request, "kr"),
        "lang_en_url": _replace_lang_in_query(request, "en"),
    }
    context.update(extra_context)
    context.update(
        {
            "meta_description": _meta_description_for_context(request, context),
            "meta_robots": "index,follow",
            "canonical_url": _absolute_public_url(request, _replace_lang_in_query(request, lang)),
            "alternate_lang_urls": {
                "ko": _absolute_public_url(request, _replace_lang_in_query(request, "kr")),
                "en": _absolute_public_url(request, _replace_lang_in_query(request, "en")),
                "x-default": _absolute_public_url(request, _replace_lang_in_query(request, "kr")),
            },
            "google_site_verification": settings.google_site_verification,
        }
    )
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


def _public_base_url(request: Request) -> str:
    settings = get_settings()
    app_domain = (settings.app_domain or "").strip().rstrip("/")
    if app_domain:
        if app_domain.startswith(("http://", "https://")):
            return app_domain
        return f"https://{app_domain}"
    return str(request.base_url).rstrip("/")


def _absolute_public_url(request: Request, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{_public_base_url(request)}{normalized_path}"


def _localized_path(path: str, lang: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}lang={lang}"


def _format_sitemap_lastmod(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.date().isoformat()


def _meta_description_for_context(request: Request, context: dict[str, object]) -> str:
    lang = cast(str, context["lang"])
    path = request.url.path
    if path.startswith("/projects/"):
        project = context.get("project")
        if isinstance(project, Project):
            summary = (project.summary_en if lang == "en" else project.summary) or (
                project.summary if lang == "en" else project.summary_en
            )
            if summary:
                return _truncate_meta_description(summary)

    page_copy = PUBLIC_SEO_COPY.get(path, PUBLIC_SEO_COPY["/"])
    return page_copy.get(lang, page_copy[DEFAULT_PUBLIC_LANG])


def _truncate_meta_description(value: str, limit: int = 160) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."

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
from app.core.constants import HOME_HERO_IMAGE_POST_SLUG, MemberRole, ProjectStatus
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
            "경희대학교 인공지능학과 박성배 교수의 자연어처리(NLP) 연구실입니다. "
            "자연어처리, 대화 시스템, 질의응답, 정보검색, 텍스트 마이닝을 연구하며 "
            "컴퓨터공학·수학·응용수학 전공 학생의 연구 참여와 대학원 진학을 환영합니다."
        ),
        "en": (
            "Kyung Hee University NLP Lab, led by Prof. Seong-Bae Park "
            "(Department of Artificial Intelligence), researches natural language "
            "processing, dialogue systems, question answering, and information retrieval."
        ),
    },
    "/members": {
        "kr": "경희대학교 인공지능학과 자연어처리 연구실의 교수와 구성원을 소개합니다.",
        "en": "Meet the members and researchers of Kyung Hee University NLP Lab.",
    },
    "/projects": {
        "kr": (
            "경희대학교 자연어처리 연구실의 연구 분야와 프로젝트를 소개합니다. "
            "자연어처리, 대화 시스템, 질의응답, 정보검색, 기계학습."
        ),
        "en": (
            "Explore natural language processing research areas and projects "
            "at Kyung Hee University NLP Lab."
        ),
    },
    "/publications": {
        "kr": "경희대학교 자연어처리 연구실의 논문과 연구 성과를 확인하세요.",
        "en": "Browse publications and research outputs from Kyung Hee University NLP Lab.",
    },
    "/contact": {
        "kr": (
            "경희대학교 자연어처리 연구실(국제캠퍼스 전자정보대학) 위치, 연락처, "
            "방문 정보를 안내합니다. 학부연구생·대학원 진학 문의를 환영합니다."
        ),
        "en": (
            "Find contact, location (International Campus, Yongin), and visit "
            "information for Kyung Hee University NLP Lab."
        ),
    },
}

PUBLIC_SEO_TITLES = {
    "/": {
        "kr": "경희대 NLP 연구실 | 경희대학교 자연어처리 연구실",
        "en": "Kyung Hee NLP Lab | Natural Language Processing Lab",
    },
    "/members": {
        "kr": "구성원 | NLP Lab",
        "en": "Members | NLP Lab",
    },
    "/projects": {
        "kr": "연구 분야 | NLP Lab",
        "en": "Research Areas | NLP Lab",
    },
    "/publications": {
        "kr": "연구성과 | NLP Lab",
        "en": "Publications | NLP Lab",
    },
    "/contact": {
        "kr": "연락처 | NLP Lab",
        "en": "Contact | NLP Lab",
    },
}

PUBLIC_STATIC_SITEMAP_PATHS = ("/", "/members", "/projects", "/publications", "/contact")

LLMS_TXT_PUBLICATION_LIMIT = 20

ORGANIZATION_NAMES = {
    "kr": "경희대학교 자연어처리 연구실",
    "en": "Kyung Hee University NLP Lab",
}

DEPARTMENT_NAMES = {
    "kr": "경희대학교 인공지능학과",
    "en": "Department of Artificial Intelligence, Kyung Hee University",
}

MEMBER_ROLE_JOB_TITLES = {
    MemberRole.PROFESSOR: "Professor",
    MemberRole.RESEARCHER: "Researcher",
    MemberRole.PHD: "PhD Student",
    MemberRole.MASTER: "Master's Student",
    MemberRole.UNDERGRAD: "Undergraduate Researcher",
}

RESEARCH_TOPICS = (
    "Natural Language Processing",
    "Machine Learning",
    "Dialogue Systems",
    "Question Answering",
    "Information Retrieval",
    "Text Mining",
    "Information Extraction",
)

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


AI_CRAWLER_USER_AGENTS = (
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-Web",
    "anthropic-ai",
    "PerplexityBot",
    "Google-Extended",
    "CCBot",
)


GOOGLE_SITE_VERIFICATION_FILENAME = "googlef810f48826f17ab4.html"
GOOGLE_SITE_VERIFICATION_FILE_CONTENT = (
    f"google-site-verification: {GOOGLE_SITE_VERIFICATION_FILENAME}"
)


@router.get(f"/{GOOGLE_SITE_VERIFICATION_FILENAME}", include_in_schema=False)
def google_site_verification_file():
    return PlainTextResponse(
        GOOGLE_SITE_VERIFICATION_FILE_CONTENT,
        media_type="text/html; charset=utf-8",
    )


@router.get("/robots.txt", include_in_schema=False)
def robots_txt(request: Request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin",
        "",
    ]
    for user_agent in AI_CRAWLER_USER_AGENTS:
        lines.extend(
            [
                f"User-agent: {user_agent}",
                "Allow: /",
                "Disallow: /admin",
                "",
            ]
        )
    lines.extend(
        [
            f"Sitemap: {_absolute_public_url(request, '/sitemap.xml')}",
            "",
        ]
    )
    return PlainTextResponse("\n".join(lines))


@router.get("/llms.txt", include_in_schema=False)
def llms_txt(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
):
    settings = get_settings()
    projects = session.exec(select(Project).order_by(col(Project.created_at).desc())).all()
    publications = session.exec(
        select(Publication)
        .order_by(col(Publication.year).desc(), col(Publication.id).desc())
        .limit(LLMS_TXT_PUBLICATION_LIMIT)
    ).all()

    lines = [
        "# Kyung Hee University NLP Lab (경희대학교 자연어처리 연구실)",
        "",
        f"> {PUBLIC_SEO_COPY['/']['en']}",
        f"> {PUBLIC_SEO_COPY['/']['kr']}",
        "",
        "## About",
        "",
        (
            "- Principal Investigator: Prof. Seong-Bae Park (박성배), "
            "Department of Artificial Intelligence (Graduate School), "
            "Kyung Hee University"
        ),
        f"- Research areas: {', '.join(RESEARCH_TOPICS)}",
        (
            "- Location: College of Electronics and Information, "
            "Kyung Hee University International Campus, Yongin, Republic of Korea"
        ),
        "",
        "## For Prospective Students (연구실 지원 안내)",
        "",
        (
            "- The lab welcomes undergraduate research interns and graduate "
            "applicants from Computer Science and Engineering (컴퓨터공학부·컴퓨터공학과), "
            "Mathematics (수학과), and Applied Mathematics (응용수학과), "
            "as well as related majors at Kyung Hee University."
        ),
        (
            "- 경희대학교 컴퓨터공학부, 수학과, 응용수학과 등 관련 전공 학부생의 "
            "학부연구생(연구실 인턴) 참여와 인공지능학과 대학원 진학을 환영합니다."
        ),
        f"- Inquiries: {settings.contact_email}",
        "",
        "## Pages",
        "",
    ]
    for path in PUBLIC_STATIC_SITEMAP_PATHS:
        title = PUBLIC_SEO_TITLES[path]["en"]
        description = PUBLIC_SEO_COPY[path]["en"]
        lines.append(f"- [{title}]({_absolute_public_url(request, path)}): {description}")

    if projects:
        lines.extend(["", "## Research Projects", ""])
        for project in projects:
            title = project.title_en or project.title
            summary = project.summary_en or project.summary
            url = _absolute_public_url(request, f"/projects/{project.slug}")
            lines.append(f"- [{title}]({url}): {summary}")

    if publications:
        lines.extend(["", "## Recent Publications", ""])
        for publication in publications:
            title = publication.title_en or publication.title
            authors = publication.authors_en or publication.authors
            venue = publication.venue_en or publication.venue
            entry = f'- {authors}. "{title}". {venue}, {publication.year}.'
            if publication.link:
                entry = f"{entry} {publication.link}"
            lines.append(entry)

    lines.extend(
        [
            "",
            "## Contact",
            "",
            f"- Email: {settings.contact_email}",
            f"- Address: {settings.contact_address}",
            "",
        ]
    )
    return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8")


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
    sitemap_entries: list[tuple[str, str | None]] = [
        (path, None) for path in PUBLIC_STATIC_SITEMAP_PATHS
    ]

    for project in projects:
        sitemap_entries.append(
            (
                f"/projects/{project.slug}",
                _format_sitemap_lastmod(project.updated_at),
            )
        )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for path, lastmod in sitemap_entries:
        alternates = (
            ("ko", _absolute_public_url(request, _localized_path(path, "kr"))),
            ("en", _absolute_public_url(request, _localized_path(path, "en"))),
            ("x-default", _absolute_public_url(request, _localized_path(path, "kr"))),
        )
        for lang in ("kr", "en"):
            localized_url = _absolute_public_url(request, _localized_path(path, lang))
            lines.append("  <url>")
            lines.append(f"    <loc>{xml_escape(localized_url)}</loc>")
            if lastmod:
                lines.append(f"    <lastmod>{lastmod}</lastmod>")
            for hreflang, href in alternates:
                escaped_href = xml_escape(href, {'"': "&quot;"})
                lines.append(
                    f'    <xhtml:link rel="alternate" hreflang="{hreflang}" '
                    f'href="{escaped_href}" />'
                )
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
            "meta_title": _meta_title_for_context(request, context),
            "meta_robots": "index,follow",
            "canonical_url": _absolute_public_url(request, _replace_lang_in_query(request, lang)),
            "alternate_lang_urls": {
                "ko": _absolute_public_url(request, _replace_lang_in_query(request, "kr")),
                "en": _absolute_public_url(request, _replace_lang_in_query(request, "en")),
                "x-default": _absolute_public_url(request, _replace_lang_in_query(request, "kr")),
            },
            "google_site_verification": settings.google_site_verification,
            "naver_site_verification": settings.naver_site_verification,
            "og_image_url": _absolute_public_url(
                request, request.url_for("static", path="images/hero.jpg").path
            ),
            "structured_data": _structured_data_for_context(request, context),
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


def _meta_title_for_context(request: Request, context: dict[str, object]) -> str:
    lang = cast(str, context["lang"])
    path = request.url.path
    if path.startswith("/projects/"):
        project = context.get("project")
        if isinstance(project, Project):
            title = (project.title_en if lang == "en" else project.title) or (
                project.title if lang == "en" else project.title_en
            )
            if title:
                return f"{title} | NLP Lab"

    page_title = PUBLIC_SEO_TITLES.get(path, PUBLIC_SEO_TITLES["/"])
    return page_title.get(lang, page_title[DEFAULT_PUBLIC_LANG])


def _truncate_meta_description(value: str, limit: int = 160) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def _organization_jsonld(request: Request, lang: str) -> dict[str, object]:
    settings = get_settings()
    alternate_lang = "kr" if lang == "en" else "en"
    return {
        "@context": "https://schema.org",
        "@type": "ResearchOrganization",
        "name": ORGANIZATION_NAMES.get(lang, ORGANIZATION_NAMES["en"]),
        "alternateName": ["NLP Lab", ORGANIZATION_NAMES[alternate_lang]],
        "url": f"{_public_base_url(request)}/",
        "logo": _absolute_public_url(
            request, request.url_for("static", path="images/logo.svg").path
        ),
        "email": settings.contact_email,
        "address": settings.contact_address,
        "parentOrganization": {
            "@type": "EducationalOrganization",
            "name": DEPARTMENT_NAMES.get(lang, DEPARTMENT_NAMES["en"]),
            "alternateName": DEPARTMENT_NAMES["kr" if lang == "en" else "en"],
            "parentOrganization": {
                "@type": "CollegeOrUniversity",
                "name": "Kyung Hee University",
                "alternateName": "경희대학교",
                "url": "https://www.khu.ac.kr",
            },
        },
        "employee": {
            "@type": "Person",
            "name": "Seong-Bae Park" if lang == "en" else "박성배",
            "alternateName": "박성배" if lang == "en" else "Seong-Bae Park",
            "jobTitle": "Professor",
            "affiliation": {
                "@type": "EducationalOrganization",
                "name": DEPARTMENT_NAMES.get(lang, DEPARTMENT_NAMES["en"]),
            },
        },
        "knowsAbout": list(RESEARCH_TOPICS),
    }


def _members_jsonld(lang: str, members: list[Member]) -> dict[str, object]:
    organization_name = ORGANIZATION_NAMES.get(lang, ORGANIZATION_NAMES["en"])
    item_list_elements: list[dict[str, object]] = []
    for position, member in enumerate(members, start=1):
        name = (member.name_en if lang == "en" else member.name) or member.name
        item_list_elements.append(
            {
                "@type": "ListItem",
                "position": position,
                "item": {
                    "@type": "Person",
                    "name": name,
                    "jobTitle": MEMBER_ROLE_JOB_TITLES.get(member.role, member.role.value),
                    "affiliation": {
                        "@type": "ResearchOrganization",
                        "name": organization_name,
                    },
                },
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": PUBLIC_SEO_TITLES["/members"].get(lang, PUBLIC_SEO_TITLES["/members"]["en"]),
        "itemListElement": item_list_elements,
    }


def _publications_jsonld(lang: str, publications: list[Publication]) -> dict[str, object]:
    item_list_elements: list[dict[str, object]] = []
    for position, publication in enumerate(publications, start=1):
        title = (publication.title_en if lang == "en" else publication.title) or publication.title
        authors = (
            publication.authors_en if lang == "en" else publication.authors
        ) or publication.authors
        venue = (publication.venue_en if lang == "en" else publication.venue) or publication.venue
        article: dict[str, object] = {
            "@type": "ScholarlyArticle",
            "name": title,
            "author": authors,
            "datePublished": str(publication.year),
            "isPartOf": {"@type": "Periodical", "name": venue},
        }
        if publication.link:
            article["url"] = publication.link
        item_list_elements.append(
            {
                "@type": "ListItem",
                "position": position,
                "item": article,
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": PUBLIC_SEO_TITLES["/publications"].get(
            lang, PUBLIC_SEO_TITLES["/publications"]["en"]
        ),
        "itemListElement": item_list_elements,
    }


def _project_jsonld(request: Request, lang: str, project: Project) -> list[dict[str, object]]:
    title = (project.title_en if lang == "en" else project.title) or project.title
    summary = (project.summary_en if lang == "en" else project.summary) or project.summary
    project_url = _absolute_public_url(request, _localized_path(f"/projects/{project.slug}", lang))
    research_project: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "ResearchProject",
        "name": title,
        "description": summary,
        "url": project_url,
        "parentOrganization": {
            "@type": "ResearchOrganization",
            "name": ORGANIZATION_NAMES.get(lang, ORGANIZATION_NAMES["en"]),
        },
    }
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home" if lang == "en" else "홈",
                "item": _absolute_public_url(request, _localized_path("/", lang)),
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Research" if lang == "en" else "연구 분야",
                "item": _absolute_public_url(request, _localized_path("/projects", lang)),
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": title,
                "item": project_url,
            },
        ],
    }
    return [research_project, breadcrumbs]


def _structured_data_for_context(
    request: Request, context: dict[str, object]
) -> list[dict[str, object]]:
    lang = cast(str, context["lang"])
    path = request.url.path
    structured_data: list[dict[str, object]] = [_organization_jsonld(request, lang)]

    if path == "/members":
        members_value = context.get("members")
        if isinstance(members_value, (list, tuple)):
            members = [item for item in members_value if isinstance(item, Member)]
            if members:
                structured_data.append(_members_jsonld(lang, members))
    elif path == "/publications":
        publications_value = context.get("publications")
        if isinstance(publications_value, (list, tuple)):
            publications = [item for item in publications_value if isinstance(item, Publication)]
            if publications:
                structured_data.append(_publications_jsonld(lang, publications))
    elif path.startswith("/projects/"):
        project = context.get("project")
        if isinstance(project, Project):
            structured_data.extend(_project_jsonld(request, lang, project))

    return structured_data

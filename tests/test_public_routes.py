from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from starlette.requests import Request

from app.core.constants import HOME_HERO_IMAGE_POST_SLUG, MemberRole, ProjectStatus
from app.main import create_app
from app.models.member import Member
from app.models.post import Post
from app.models.project import Project
from app.models.publication import Publication
from app.routers.public import (
    contact_page,
    home,
    members_page,
    project_detail_page,
    projects_page,
    publications_page,
)


def _dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=hours)


def _make_request(app: FastAPI, path: str, query_string: str = "") -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": query_string.encode("utf-8"),
        "headers": [],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "root_path": "",
        "app": app,
    }
    return Request(scope)


@pytest.fixture
def app_and_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    app = create_app()
    return app, engine


def _seed_baseline(engine) -> str:
    with Session(engine) as session:
        project = Project(
            title="project-baseline",
            slug="project-baseline",
            summary="baseline summary",
            description="baseline description",
            status=ProjectStatus.ONGOING,
            start_date=date(2025, 1, 1),
            end_date=None,
            created_at=_dt(1),
            updated_at=_dt(1),
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        session.add(
            Member(
                name="member-baseline",
                role=MemberRole.RESEARCHER,
                email="member-baseline@example.com",
                photo_url=None,
                bio="baseline bio",
                display_order=1,
                created_at=_dt(1),
                updated_at=_dt(1),
            )
        )
        session.add(
            Publication(
                title="publication-baseline",
                authors="a1, a2",
                venue="venue",
                year=2025,
                link=None,
                related_project_id=project.id,
                created_at=_dt(1),
            )
        )
        session.add(
            Post(
                title="post-baseline",
                slug="post-baseline",
                content="baseline content",
                is_published=True,
                created_at=_dt(1),
                updated_at=_dt(1),
            )
        )
        session.commit()
    return "project-baseline"


def test_public_routes_return_200(app_and_engine):
    app, engine = app_and_engine
    project_slug = _seed_baseline(engine)

    with Session(engine) as session:
        assert home(_make_request(app, "/"), session=session).status_code == 200
        assert members_page(_make_request(app, "/members"), session=session).status_code == 200
        assert projects_page(_make_request(app, "/projects"), session=session).status_code == 200
        assert (
            project_detail_page(
                _make_request(app, f"/projects/{project_slug}"),
                slug=project_slug,
                session=session,
            ).status_code
            == 200
        )
        assert (
            publications_page(_make_request(app, "/publications"), session=session).status_code
            == 200
        )
    assert contact_page(_make_request(app, "/contact")).status_code == 200


def test_public_routes_support_en_language_query(app_and_engine):
    app, engine = app_and_engine
    project_slug = _seed_baseline(engine)

    with Session(engine) as session:
        responses = [
            home(_make_request(app, "/", query_string="lang=en"), session=session),
            members_page(_make_request(app, "/members", query_string="lang=en"), session=session),
            projects_page(_make_request(app, "/projects", query_string="lang=en"), session=session),
            project_detail_page(
                _make_request(app, f"/projects/{project_slug}", query_string="lang=en"),
                slug=project_slug,
                session=session,
            ),
            publications_page(
                _make_request(app, "/publications", query_string="lang=en"),
                session=session,
            ),
            contact_page(_make_request(app, "/contact", query_string="lang=en")),
        ]

    for response in responses:
        assert response.status_code == 200
        assert response.context["lang"] == "en"
        assert response.context["is_en"] is True
        assert response.context["lang_kr_url"].startswith(response.context["request"].url.path)
        assert "nlp_lang=en" in response.headers["set-cookie"]


def test_members_page_displays_language_specific_name_and_bio_with_fallback(app_and_engine):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app, engine = app_and_engine
    with Session(engine) as session:
        session.add_all(
            [
                Member(
                    name="홍길동",
                    name_en="Hong Gil-dong",
                    role=MemberRole.RESEARCHER,
                    email="member-a@example.com",
                    photo_url=None,
                    bio="한글 소개 A",
                    bio_en="English Intro A",
                    display_order=1,
                    created_at=_dt(1),
                    updated_at=_dt(1),
                ),
                Member(
                    name="이멤버",
                    name_en=None,
                    role=MemberRole.PHD,
                    email="member-b@example.com",
                    photo_url=None,
                    bio="한글 소개 B",
                    bio_en=None,
                    display_order=2,
                    created_at=_dt(2),
                    updated_at=_dt(2),
                ),
                Member(
                    name="박멤버",
                    name_en="Park Member",
                    role=MemberRole.MASTER,
                    email="member-c@example.com",
                    photo_url=None,
                    bio=None,
                    bio_en="English Intro C",
                    display_order=3,
                    created_at=_dt(3),
                    updated_at=_dt(3),
                ),
            ]
        )
        session.commit()

    client = TestClient(app)

    ko_response = client.get("/members?lang=kr")
    assert ko_response.status_code == 200
    assert "홍길동" in ko_response.text
    assert "한글 소개 A" in ko_response.text
    assert "English Intro A" not in ko_response.text
    assert "English Intro C" in ko_response.text

    en_response = client.get("/members?lang=en")
    assert en_response.status_code == 200
    assert "Hong Gil-dong" in en_response.text
    assert "English Intro A" in en_response.text
    assert "한글 소개 A" not in en_response.text
    assert "이멤버" in en_response.text
    assert "한글 소개 B" in en_response.text
    assert "Park Member" in en_response.text
    assert "English Intro C" in en_response.text


def test_project_publication_post_pages_display_language_content_with_fallback(app_and_engine):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app, engine = app_and_engine
    with Session(engine) as session:
        bilingual_project = Project(
            title="프로젝트-국문",
            title_en="PROJECT_EN_ONLY",
            slug="project-lang-a",
            summary="PROJECT_SUMMARY_KR_ONLY",
            summary_en="PROJECT_SUMMARY_EN_ONLY",
            description="PROJECT_DESC_KR_ONLY",
            description_en="PROJECT_DESC_EN_ONLY",
            status=ProjectStatus.ONGOING,
            start_date=date(2025, 1, 1),
            end_date=None,
            created_at=_dt(1),
            updated_at=_dt(1),
        )
        fallback_project = Project(
            title="PROJECT_FALLBACK_KR_ONLY",
            title_en=None,
            slug="project-lang-b",
            summary="PROJECT_FALLBACK_SUMMARY_KR_ONLY",
            summary_en=None,
            description="PROJECT_FALLBACK_DESC_KR_ONLY",
            description_en=None,
            status=ProjectStatus.COMPLETED,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            created_at=_dt(2),
            updated_at=_dt(2),
        )
        session.add_all([bilingual_project, fallback_project])
        session.commit()
        session.refresh(bilingual_project)

        session.add_all(
            [
                Publication(
                    title="PUBLICATION_KR_ONLY",
                    title_en="PUBLICATION_EN_ONLY",
                    authors="AUTHORS_KR_ONLY",
                    authors_en="AUTHORS_EN_ONLY",
                    venue="VENUE_KR_ONLY",
                    venue_en="VENUE_EN_ONLY",
                    year=2026,
                    link=None,
                    related_project_id=bilingual_project.id,
                    created_at=_dt(3),
                ),
                Publication(
                    title="PUBLICATION_FALLBACK_KR_ONLY",
                    title_en=None,
                    authors="AUTHORS_FALLBACK_KR_ONLY",
                    authors_en=None,
                    venue="VENUE_FALLBACK_KR_ONLY",
                    venue_en=None,
                    year=2025,
                    link=None,
                    related_project_id=bilingual_project.id,
                    created_at=_dt(4),
                ),
                Post(
                    title="POST_KR_ONLY",
                    title_en="POST_EN_ONLY",
                    slug="post-lang-a",
                    content="POST_CONTENT_KR_ONLY",
                    content_en="POST_CONTENT_EN_ONLY",
                    is_published=True,
                    created_at=_dt(5),
                    updated_at=_dt(5),
                ),
                Post(
                    title="POST_FALLBACK_KR_ONLY",
                    title_en=None,
                    slug="post-lang-b",
                    content="POST_FALLBACK_CONTENT_KR_ONLY",
                    content_en=None,
                    is_published=True,
                    created_at=_dt(6),
                    updated_at=_dt(6),
                ),
            ]
        )
        session.commit()

    client = TestClient(app)

    projects_ko = client.get("/projects?lang=kr")
    assert projects_ko.status_code == 200
    assert "프로젝트-국문" in projects_ko.text
    assert "PROJECT_SUMMARY_KR_ONLY" in projects_ko.text
    assert "PROJECT_EN_ONLY" not in projects_ko.text

    projects_en = client.get("/projects?lang=en")
    assert projects_en.status_code == 200
    assert "PROJECT_EN_ONLY" in projects_en.text
    assert "PROJECT_SUMMARY_EN_ONLY" in projects_en.text
    assert "PROJECT_FALLBACK_KR_ONLY" in projects_en.text
    assert "PROJECT_FALLBACK_SUMMARY_KR_ONLY" in projects_en.text

    project_detail_en = client.get("/projects/project-lang-a?lang=en")
    assert project_detail_en.status_code == 200
    assert "PROJECT_EN_ONLY" in project_detail_en.text
    assert "PROJECT_DESC_EN_ONLY" in project_detail_en.text
    assert "PUBLICATION_EN_ONLY" in project_detail_en.text
    assert "AUTHORS_EN_ONLY" in project_detail_en.text
    assert "VENUE_EN_ONLY" in project_detail_en.text

    publications_en = client.get("/publications?lang=en")
    assert publications_en.status_code == 200
    assert "PUBLICATION_EN_ONLY" in publications_en.text
    assert "AUTHORS_EN_ONLY" in publications_en.text
    assert "VENUE_EN_ONLY" in publications_en.text
    assert "PUBLICATION_FALLBACK_KR_ONLY" in publications_en.text
    assert "AUTHORS_FALLBACK_KR_ONLY" in publications_en.text

    home_en = client.get("/?lang=en")
    assert home_en.status_code == 200
    assert "POST_EN_ONLY" in home_en.text
    assert "POST_CONTENT_EN_ONLY" in home_en.text
    assert "POST_FALLBACK_KR_ONLY" in home_en.text
    assert "POST_FALLBACK_CONTENT_KR_ONLY" in home_en.text


def test_project_detail_returns_404_for_unknown_slug(app_and_engine):
    app, engine = app_and_engine
    with Session(engine) as session:
        with pytest.raises(HTTPException) as exc_info:
            project_detail_page(
                _make_request(app, "/projects/does-not-exist"),
                slug="does-not-exist",
                session=session,
            )
    assert exc_info.value.status_code == 404


def test_home_sorting_rules_and_limits(app_and_engine):
    app, engine = app_and_engine
    with Session(engine) as session:
        session.add_all(
            [
                Project(
                    title="project-oldest",
                    slug="project-oldest",
                    summary="s1",
                    description="d1",
                    status=ProjectStatus.ONGOING,
                    start_date=date(2024, 1, 1),
                    end_date=None,
                    created_at=_dt(1),
                    updated_at=_dt(1),
                ),
                Project(
                    title="project-middle",
                    slug="project-middle",
                    summary="s2",
                    description="d2",
                    status=ProjectStatus.ONGOING,
                    start_date=date(2024, 2, 1),
                    end_date=None,
                    created_at=_dt(2),
                    updated_at=_dt(2),
                ),
                Project(
                    title="project-new",
                    slug="project-new",
                    summary="s3",
                    description="d3",
                    status=ProjectStatus.COMPLETED,
                    start_date=date(2024, 3, 1),
                    end_date=date(2024, 12, 31),
                    created_at=_dt(3),
                    updated_at=_dt(3),
                ),
                Project(
                    title="project-newest",
                    slug="project-newest",
                    summary="s4",
                    description="d4",
                    status=ProjectStatus.ONGOING,
                    start_date=date(2024, 4, 1),
                    end_date=None,
                    created_at=_dt(4),
                    updated_at=_dt(4),
                ),
            ]
        )
        session.add_all(
            [
                Publication(
                    title="publication-2026",
                    authors="authors",
                    venue="venue",
                    year=2026,
                    link=None,
                    related_project_id=None,
                    created_at=_dt(1),
                ),
                Publication(
                    title="publication-2025-a",
                    authors="authors",
                    venue="venue",
                    year=2025,
                    link=None,
                    related_project_id=None,
                    created_at=_dt(1),
                ),
                Publication(
                    title="publication-2025-b",
                    authors="authors",
                    venue="venue",
                    year=2025,
                    link=None,
                    related_project_id=None,
                    created_at=_dt(1),
                ),
                Publication(
                    title="publication-2024",
                    authors="authors",
                    venue="venue",
                    year=2024,
                    link=None,
                    related_project_id=None,
                    created_at=_dt(1),
                ),
                Publication(
                    title="publication-2023",
                    authors="authors",
                    venue="venue",
                    year=2023,
                    link=None,
                    related_project_id=None,
                    created_at=_dt(1),
                ),
                Publication(
                    title="publication-2022",
                    authors="authors",
                    venue="venue",
                    year=2022,
                    link=None,
                    related_project_id=None,
                    created_at=_dt(1),
                ),
            ]
        )
        session.add_all(
            [
                Post(
                    title="post-oldest",
                    slug="post-oldest",
                    content="c1",
                    is_published=True,
                    created_at=_dt(1),
                    updated_at=_dt(1),
                ),
                Post(
                    title="post-middle",
                    slug="post-middle",
                    content="c2",
                    is_published=True,
                    created_at=_dt(2),
                    updated_at=_dt(2),
                ),
                Post(
                    title="post-new",
                    slug="post-new",
                    content="c3",
                    is_published=True,
                    created_at=_dt(3),
                    updated_at=_dt(3),
                ),
                Post(
                    title="post-newest",
                    slug="post-newest",
                    content="c4",
                    is_published=True,
                    created_at=_dt(4),
                    updated_at=_dt(4),
                ),
                Post(
                    title="post-unpublished",
                    slug="post-unpublished",
                    content="c5",
                    is_published=False,
                    created_at=_dt(5),
                    updated_at=_dt(5),
                ),
                Post(
                    title="home-hero-image",
                    slug=HOME_HERO_IMAGE_POST_SLUG,
                    content="/static/images/custom-hero.jpg\n/static/images/custom-hero-2.jpg",
                    is_published=True,
                    created_at=_dt(6),
                    updated_at=_dt(6),
                ),
            ]
        )
        session.commit()

        response = home(_make_request(app, "/"), session=session)

    assert response.status_code == 200

    project_titles = [project.title for project in response.context["projects"]]
    assert project_titles == ["project-newest", "project-new", "project-middle"]

    publication_titles = [publication.title for publication in response.context["publications"]]
    assert publication_titles == [
        "publication-2026",
        "publication-2025-b",
        "publication-2025-a",
        "publication-2024",
        "publication-2023",
    ]

    post_titles = [post.title for post in response.context["posts"]]
    assert post_titles == ["post-newest", "post-new", "post-middle"]
    assert "post-unpublished" not in post_titles
    assert response.context["hero_images"] == [
        "/static/images/custom-hero.jpg",
        "/static/images/custom-hero-2.jpg",
    ]
    assert response.context["hero_image_url"] == "/static/images/custom-hero.jpg"


def test_home_hero_image_path_is_normalized_to_static(app_and_engine):
    app, engine = app_and_engine
    with Session(engine) as session:
        session.add(
            Post(
                title="home-hero-image",
                slug=HOME_HERO_IMAGE_POST_SLUG,
                content="images/relative-hero.jpg",
                is_published=True,
                created_at=_dt(1),
                updated_at=_dt(1),
            )
        )
        session.commit()

        response = home(_make_request(app, "/"), session=session)

    assert response.status_code == 200
    assert response.context["hero_images"] == ["/static/images/relative-hero.jpg"]


def test_home_hero_image_old_default_path_is_normalized(app_and_engine):
    app, engine = app_and_engine
    with Session(engine) as session:
        session.add(
            Post(
                title="home-hero-image",
                slug=HOME_HERO_IMAGE_POST_SLUG,
                content="/static/images/hero.jpg",
                is_published=True,
                created_at=_dt(1),
                updated_at=_dt(1),
            )
        )
        session.commit()

        response = home(_make_request(app, "/"), session=session)

    assert response.status_code == 200
    assert response.context["hero_images"] == ["/static/images/hero/hero.jpg"]


def test_project_detail_shows_only_related_publications(app_and_engine):
    app, engine = app_and_engine
    with Session(engine) as session:
        first_project = Project(
            title="project-one",
            slug="project-one",
            summary="summary one",
            description="description one",
            status=ProjectStatus.ONGOING,
            start_date=date(2024, 1, 1),
            end_date=None,
            created_at=_dt(1),
            updated_at=_dt(1),
        )
        second_project = Project(
            title="project-two",
            slug="project-two",
            summary="summary two",
            description="description two",
            status=ProjectStatus.COMPLETED,
            start_date=date(2024, 2, 1),
            end_date=date(2024, 12, 1),
            created_at=_dt(2),
            updated_at=_dt(2),
        )
        session.add(first_project)
        session.add(second_project)
        session.commit()
        session.refresh(first_project)
        session.refresh(second_project)

        session.add(
            Publication(
                title="publication-related",
                authors="authors",
                venue="venue",
                year=2025,
                link=None,
                related_project_id=first_project.id,
                created_at=_dt(1),
            )
        )
        session.add(
            Publication(
                title="publication-unrelated",
                authors="authors",
                venue="venue",
                year=2025,
                link=None,
                related_project_id=second_project.id,
                created_at=_dt(1),
            )
        )
        session.commit()

        response = project_detail_page(
            _make_request(app, "/projects/project-one"),
            slug="project-one",
            session=session,
        )

    assert response.status_code == 200
    publication_titles = [publication.title for publication in response.context["publications"]]
    assert publication_titles == ["publication-related"]


def test_projects_page_renders_status_filter_links(app_and_engine):
    app, engine = app_and_engine
    with Session(engine) as session:
        session.add_all(
            [
                Project(
                    title="project-ongoing",
                    slug="project-ongoing",
                    summary="summary ongoing",
                    description="description ongoing",
                    status=ProjectStatus.ONGOING,
                    start_date=date(2024, 1, 1),
                    end_date=None,
                    created_at=_dt(1),
                    updated_at=_dt(1),
                ),
                Project(
                    title="project-completed",
                    slug="project-completed",
                    summary="summary completed",
                    description="description completed",
                    status=ProjectStatus.COMPLETED,
                    start_date=date(2023, 1, 1),
                    end_date=date(2023, 12, 31),
                    created_at=_dt(2),
                    updated_at=_dt(2),
                ),
            ]
        )
        session.commit()

        response = projects_page(
            _make_request(app, "/projects", query_string="status=ongoing&lang=en"),
            session=session,
            status=ProjectStatus.ONGOING,
        )

    assert response.status_code == 200
    assert response.context["selected_status"] == "ongoing"
    body = response.body.decode("utf-8")
    assert "/projects?lang=en" in body
    assert "/projects?status=ongoing&amp;lang=en" in body
    assert "/projects?status=completed&amp;lang=en" in body


def test_publications_page_renders_year_filter_links(app_and_engine):
    app, engine = app_and_engine
    with Session(engine) as session:
        session.add_all(
            [
                Publication(
                    title="publication-2026",
                    authors="authors",
                    venue="venue",
                    year=2026,
                    link=None,
                    related_project_id=None,
                    created_at=_dt(1),
                ),
                Publication(
                    title="publication-2025",
                    authors="authors",
                    venue="venue",
                    year=2025,
                    link=None,
                    related_project_id=None,
                    created_at=_dt(2),
                ),
            ]
        )
        session.commit()

        response = publications_page(
            _make_request(app, "/publications", query_string="year=2025&lang=en"),
            session=session,
            year=2025,
        )

    assert response.status_code == 200
    assert response.context["selected_year"] == 2025
    assert response.context["years"] == [2026, 2025]
    body = response.body.decode("utf-8")
    assert "/publications?lang=en" in body
    assert "/publications?year=2025&amp;lang=en" in body
    assert "/publications?year=2026&amp;lang=en" in body

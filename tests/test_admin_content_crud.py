"""Project, publication, and post CRUD integration tests."""

from __future__ import annotations

import asyncio
import re
from datetime import date
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from starlette.types import Message, Receive, Scope, Send

from app.core.constants import HOME_HERO_IMAGE_POST_SLUG, ProjectStatus
from app.core.security import hash_password
from app.db.session import get_session
from app.main import create_app
from app.models.admin_user import AdminUser
from app.models.post import Post
from app.models.project import Project
from app.models.publication import Publication
from app.routers import admin_post


def _header_value(headers: list[tuple[str, str]], name: str) -> str | None:
    for key, value in headers:
        if key.lower() == name.lower():
            return value
    return None


def _update_cookie_jar(cookie_jar: dict[str, str], headers: list[tuple[str, str]]) -> None:
    for key, value in headers:
        if key.lower() != "set-cookie":
            continue
        parsed_cookie = SimpleCookie()
        parsed_cookie.load(value)
        for morsel in parsed_cookie.values():
            cookie_jar[morsel.key] = morsel.value


def _extract_csrf_token(body: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert match is not None
    return match.group(1)


def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    form: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> tuple[int, list[tuple[str, str]], str]:
    headers: list[tuple[bytes, bytes]] = [(b"host", b"testserver")]
    request_body = b""

    if cookies:
        cookie_header = "; ".join(f"{name}={value}" for name, value in cookies.items())
        headers.append((b"cookie", cookie_header.encode("utf-8")))

    if form is not None:
        request_body = urlencode(form).encode("utf-8")
        headers.extend(
            [
                (b"content-type", b"application/x-www-form-urlencoded"),
                (b"content-length", str(len(request_body)).encode("utf-8")),
            ]
        )
    else:
        headers.append((b"content-length", b"0"))

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "root_path": "",
    }

    sent = False

    async def receive() -> Message:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": request_body, "more_body": False}

    messages: list[Message] = []

    async def send(message: Message) -> None:
        messages.append(message)

    receive_fn: Receive = receive
    send_fn: Send = send
    asyncio.run(app(scope, receive_fn, send_fn))

    status_code = 500
    response_headers: list[tuple[str, str]] = []
    body = b""
    for message in messages:
        if message["type"] == "http.response.start":
            status_code = message["status"]
            response_headers = [
                (key.decode("latin-1"), value.decode("latin-1"))
                for key, value in message.get("headers", [])
            ]
        if message["type"] == "http.response.body":
            body += message.get("body", b"")

    return status_code, response_headers, body.decode("utf-8", errors="ignore")


@pytest.fixture
def app_and_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            AdminUser(
                username="admin",
                password_hash=hash_password("test-password"),
            )
        )
        session.commit()

    app = create_app()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    return app, engine


def _login_as_admin(app: FastAPI, cookie_jar: dict[str, str]) -> None:
    status_code, headers, login_body = _request(app, "GET", "/admin/login")
    _update_cookie_jar(cookie_jar, headers)
    csrf_token = _extract_csrf_token(login_body)

    assert status_code == 200

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/login",
        form={
            "username": "admin",
            "password": "test-password",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )
    _update_cookie_jar(cookie_jar, headers)

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin"


def _get_csrf_token(app: FastAPI, cookie_jar: dict[str, str], path: str) -> str:
    status_code, headers, body = _request(app, "GET", path, cookies=cookie_jar)
    _update_cookie_jar(cookie_jar, headers)

    assert status_code == 200
    return _extract_csrf_token(body)


def test_project_create_update_delete_flow(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/projects")

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/projects",
        form={
            "title": "NLP Platform",
            "title_en": "NLP Platform EN",
            "slug": "nlp-platform",
            "summary": "초기 요약",
            "summary_en": "Initial summary",
            "description": "프로젝트 상세 설명",
            "description_en": "Project detail description",
            "status": "ongoing",
            "start_date": "2024-03-01",
            "end_date": "",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/projects"

    with Session(engine) as session:
        project = session.exec(select(Project).where(Project.slug == "nlp-platform")).first()
        assert project is not None
        assert project.title == "NLP Platform"
        assert project.title_en == "NLP Platform EN"
        assert project.summary_en == "Initial summary"
        assert project.description_en == "Project detail description"
        assert project.status == ProjectStatus.ONGOING
        assert project.start_date == date(2024, 3, 1)
        project_id = project.id

    assert project_id is not None
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/projects")

    status_code, headers, _ = _request(
        app,
        "POST",
        f"/admin/projects/{project_id}/update",
        form={
            "title": "NLP Platform v2",
            "title_en": "NLP Platform v2 EN",
            "slug": "nlp-platform-v2",
            "summary": "수정 요약",
            "summary_en": "Updated summary",
            "description": "수정된 설명",
            "description_en": "Updated description",
            "status": "completed",
            "start_date": "2024-03-01",
            "end_date": "2025-01-10",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/projects"

    with Session(engine) as session:
        updated_project = session.get(Project, project_id)
        assert updated_project is not None
        assert updated_project.title == "NLP Platform v2"
        assert updated_project.title_en == "NLP Platform v2 EN"
        assert updated_project.slug == "nlp-platform-v2"
        assert updated_project.summary_en == "Updated summary"
        assert updated_project.description_en == "Updated description"
        assert updated_project.status == ProjectStatus.COMPLETED
        assert updated_project.end_date == date(2025, 1, 10)

    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/projects")
    status_code, headers, _ = _request(
        app,
        "POST",
        f"/admin/projects/{project_id}/delete",
        form={"csrf_token": csrf_token},
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/projects"

    with Session(engine) as session:
        assert session.get(Project, project_id) is None


def test_project_create_rejects_invalid_csrf(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    _ = _get_csrf_token(app, cookie_jar, "/admin/projects")

    status_code, _, _ = _request(
        app,
        "POST",
        "/admin/projects",
        form={
            "title": "Blocked Project",
            "slug": "blocked-project",
            "summary": "요약",
            "description": "설명",
            "status": "ongoing",
            "start_date": "2025-01-01",
            "end_date": "",
            "csrf_token": "invalid-token",
        },
        cookies=cookie_jar,
    )

    assert status_code == 403
    with Session(engine) as session:
        assert session.exec(select(Project)).all() == []


def test_project_create_accepts_english_only_fields(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/projects")

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/projects",
        form={
            "title": "",
            "title_en": "Project EN Only",
            "slug": "project-en-only",
            "summary": "",
            "summary_en": "Summary EN Only",
            "description": "",
            "description_en": "Description EN Only",
            "status": "ongoing",
            "start_date": "2025-01-01",
            "end_date": "",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/projects"

    with Session(engine) as session:
        project = session.exec(select(Project).where(Project.slug == "project-en-only")).first()
        assert project is not None
        assert project.title == "Project EN Only"
        assert project.title_en == "Project EN Only"
        assert project.summary == "Summary EN Only"
        assert project.summary_en == "Summary EN Only"
        assert project.description == "Description EN Only"
        assert project.description_en == "Description EN Only"


def test_publication_create_update_delete_flow(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}

    with Session(engine) as session:
        related_project = Project(
            title="Linked Project",
            slug="linked-project",
            summary="연계 요약",
            description="연계 설명",
            status=ProjectStatus.ONGOING,
            start_date=date(2024, 1, 1),
        )
        session.add(related_project)
        session.commit()
        session.refresh(related_project)
        related_project_id = related_project.id

    assert related_project_id is not None
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/publications")

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/publications",
        form={
            "title": "NLP Paper",
            "title_en": "NLP Paper EN",
            "authors": "Author A, Author B",
            "authors_en": "Author A, Author B EN",
            "venue": "ACL",
            "venue_en": "ACL EN",
            "year": "2025",
            "link": "https://example.com/paper",
            "related_project_id": str(related_project_id),
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/publications"

    with Session(engine) as session:
        publication = session.exec(
            select(Publication).where(Publication.title == "NLP Paper")
        ).first()
        assert publication is not None
        assert publication.title_en == "NLP Paper EN"
        assert publication.authors_en == "Author A, Author B EN"
        assert publication.venue_en == "ACL EN"
        assert publication.year == 2025
        assert publication.related_project_id == related_project_id
        publication_id = publication.id

    assert publication_id is not None
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/publications")

    status_code, headers, _ = _request(
        app,
        "POST",
        f"/admin/publications/{publication_id}/update",
        form={
            "title": "NLP Paper Revised",
            "title_en": "",
            "authors": "Author A",
            "authors_en": "",
            "venue": "EMNLP",
            "venue_en": "",
            "year": "2026",
            "link": "",
            "related_project_id": "",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/publications"

    with Session(engine) as session:
        updated_publication = session.get(Publication, publication_id)
        assert updated_publication is not None
        assert updated_publication.title == "NLP Paper Revised"
        assert updated_publication.title_en is None
        assert updated_publication.venue == "EMNLP"
        assert updated_publication.authors_en is None
        assert updated_publication.venue_en is None
        assert updated_publication.year == 2026
        assert updated_publication.link is None
        assert updated_publication.related_project_id is None

    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/publications")
    status_code, headers, _ = _request(
        app,
        "POST",
        f"/admin/publications/{publication_id}/delete",
        form={"csrf_token": csrf_token},
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/publications"

    with Session(engine) as session:
        assert session.get(Publication, publication_id) is None


def test_publication_create_rejects_invalid_csrf(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    _ = _get_csrf_token(app, cookie_jar, "/admin/publications")

    status_code, _, _ = _request(
        app,
        "POST",
        "/admin/publications",
        form={
            "title": "Blocked Publication",
            "authors": "Author",
            "venue": "Venue",
            "year": "2025",
            "link": "",
            "related_project_id": "",
            "csrf_token": "invalid-token",
        },
        cookies=cookie_jar,
    )

    assert status_code == 403
    with Session(engine) as session:
        assert session.exec(select(Publication)).all() == []


def test_publication_create_accepts_english_only_fields(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/publications")

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/publications",
        form={
            "title": "",
            "title_en": "Publication EN Only",
            "authors": "",
            "authors_en": "Authors EN Only",
            "venue": "",
            "venue_en": "Venue EN Only",
            "year": "2026",
            "link": "",
            "related_project_id": "",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/publications"

    with Session(engine) as session:
        publication = session.exec(
            select(Publication).where(Publication.title == "Publication EN Only")
        ).first()
        assert publication is not None
        assert publication.title_en == "Publication EN Only"
        assert publication.authors == "Authors EN Only"
        assert publication.authors_en == "Authors EN Only"
        assert publication.venue == "Venue EN Only"
        assert publication.venue_en == "Venue EN Only"


def test_publication_create_rejects_unsafe_link_scheme(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/publications")

    status_code, _, body = _request(
        app,
        "POST",
        "/admin/publications",
        form={
            "title": "Blocked Publication",
            "authors": "Author",
            "venue": "Venue",
            "year": "2025",
            "link": "javascript:alert(1)",
            "related_project_id": "",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 400
    assert "논문 입력값을 확인해주세요." in body
    with Session(engine) as session:
        assert session.exec(select(Publication)).all() == []


def test_post_create_update_delete_flow(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/posts")

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/posts",
        form={
            "title": "공지사항",
            "title_en": "Notice",
            "slug": "notice-1",
            "content": "초기 공지 내용",
            "content_en": "Initial notice content",
            "is_published": "true",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/posts"

    with Session(engine) as session:
        post = session.exec(select(Post).where(Post.slug == "notice-1")).first()
        assert post is not None
        assert post.title_en == "Notice"
        assert post.content_en == "Initial notice content"
        assert post.is_published is True
        post_id = post.id

    assert post_id is not None
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/posts")

    status_code, headers, _ = _request(
        app,
        "POST",
        f"/admin/posts/{post_id}/update",
        form={
            "title": "공지사항 수정",
            "title_en": "",
            "slug": "notice-1-updated",
            "content": "수정 공지 내용",
            "content_en": "",
            "is_published": "false",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/posts"

    with Session(engine) as session:
        updated_post = session.get(Post, post_id)
        assert updated_post is not None
        assert updated_post.slug == "notice-1-updated"
        assert updated_post.content == "수정 공지 내용"
        assert updated_post.title_en is None
        assert updated_post.content_en is None
        assert updated_post.is_published is False

    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/posts")
    status_code, headers, _ = _request(
        app,
        "POST",
        f"/admin/posts/{post_id}/delete",
        form={"csrf_token": csrf_token},
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/posts"

    with Session(engine) as session:
        assert session.get(Post, post_id) is None


def test_post_create_accepts_english_only_fields(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/posts")

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/posts",
        form={
            "title": "",
            "title_en": "Post EN Only",
            "slug": "post-en-only",
            "content": "",
            "content_en": "Content EN Only",
            "is_published": "true",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/posts"

    with Session(engine) as session:
        post = session.exec(select(Post).where(Post.slug == "post-en-only")).first()
        assert post is not None
        assert post.title == "Post EN Only"
        assert post.title_en == "Post EN Only"
        assert post.content == "Content EN Only"
        assert post.content_en == "Content EN Only"


def test_home_hero_image_create_update_flow_via_posts_crud(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/posts")

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/posts",
        form={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": "/static/images/hero-new.jpg\n/static/images/hero-new-2.jpg",
            "is_published": "false",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.exec(select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)).first()
        assert hero_post is not None
        assert hero_post.content == "/static/images/hero-new.jpg\n/static/images/hero-new-2.jpg"
        assert hero_post.is_published is False
        hero_post_id = hero_post.id

    assert hero_post_id is not None
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/posts")

    status_code, headers, _ = _request(
        app,
        "POST",
        f"/admin/posts/{hero_post_id}/update",
        form={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": "/static/images/hero-updated.jpg\n/static/images/hero-updated-2.jpg",
            "is_published": "false",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/posts"

    with Session(engine) as session:
        updated_hero_post = session.get(Post, hero_post_id)
        assert updated_hero_post is not None
        assert (
            updated_hero_post.content
            == "/static/images/hero-updated.jpg\n/static/images/hero-updated-2.jpg"
        )
        assert updated_hero_post.is_published is False

    status_code, _, body = _request(app, "GET", "/")
    assert status_code == 200
    assert 'src="/static/images/hero-updated.jpg"' in body
    assert "/static/images/hero-updated-2.jpg" in body


def test_home_hero_image_create_with_empty_content_uses_default(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_csrf_token(app, cookie_jar, "/admin/posts")

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/posts",
        form={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": "",
            "is_published": "false",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.exec(select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)).first()
        assert hero_post is not None
        assert hero_post.content == "/static/images/hero/hero.jpg"

    status_code, _, body = _request(app, "GET", "/")
    assert status_code == 200
    assert 'src="/static/images/hero/hero.jpg"' in body


def test_home_hero_image_upload_uses_uploaded_filename(app_and_engine):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app, engine = app_and_engine
    client = TestClient(app)

    login_body = client.get("/admin/login").text
    login_csrf_token = _extract_csrf_token(login_body)
    response = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "test-password",
            "csrf_token": login_csrf_token,
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"

    posts_body = client.get("/admin/posts").text
    posts_csrf_token = _extract_csrf_token(posts_body)

    response = client.post(
        "/admin/posts",
        data={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": "",
            "is_published": "false",
            "csrf_token": posts_csrf_token,
        },
        files={
            "hero_image_files": (
                "rename-able-name.png",
                b"\x89PNG\r\n\x1a\n" + b"1" * 16,
                "image/png",
            )
        },
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.exec(select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)).first()
        assert hero_post is not None
        assert hero_post.content == "/static/images/rename-able-name.png"

        image_path = (
            Path(__file__).resolve().parents[1] / "app/static/images/hero/rename-able-name.png"
        )
        if image_path.exists():
            image_path.unlink()


def test_home_hero_image_upload_keeps_fallback(app_and_engine):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app, engine = app_and_engine
    client = TestClient(app)

    login_body = client.get("/admin/login").text
    login_csrf_token = _extract_csrf_token(login_body)
    response = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "test-password",
            "csrf_token": login_csrf_token,
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"

    posts_body = client.get("/admin/posts").text
    posts_csrf_token = _extract_csrf_token(posts_body)

    response = client.post(
        "/admin/posts",
        data={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": "/static/images/hero/hero.jpg",
            "is_published": "false",
            "csrf_token": posts_csrf_token,
        },
        files={
            "hero_image_files": (
                "fallback-append.png",
                b"\x89PNG\r\n\x1a\n" + b"6" * 16,
                "image/png",
            )
        },
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"

    hero_image_path = None
    uploaded_image_url: str | None = None

    try:
        with Session(engine) as session:
            hero_post = session.exec(
                select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)
            ).first()
            assert hero_post is not None
            hero_urls = [line for line in hero_post.content.splitlines() if line.strip()]
            assert hero_urls[0] == "/static/images/hero/hero.jpg"
            assert len(hero_urls) == 2
            uploaded_image_url = hero_urls[1]
            assert uploaded_image_url.startswith("/static/images/hero/")
            assert uploaded_image_url.endswith(".png")

            hero_image_path = (
                Path(__file__).resolve().parents[1]
                / "app/static/images/hero"
                / uploaded_image_url.removeprefix("/static/images/hero/")
            )
            assert hero_image_path.exists()

        home_body = client.get("/")
        assert home_body.status_code == 200
        assert f'src="{hero_urls[0]}"' in home_body.text
        assert f'src="{hero_urls[1]}"' in home_body.text
    finally:
        if hero_image_path is not None and hero_image_path.exists():
            hero_image_path.unlink()


def test_home_hero_image_rename_uploaded_filename(app_and_engine):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app, engine = app_and_engine
    client = TestClient(app)

    login_body = client.get("/admin/login").text
    login_csrf_token = _extract_csrf_token(login_body)
    response = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "test-password",
            "csrf_token": login_csrf_token,
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"

    posts_body = client.get("/admin/posts").text
    posts_csrf_token = _extract_csrf_token(posts_body)

    response = client.post(
        "/admin/posts",
        data={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": "",
            "is_published": "false",
            "csrf_token": posts_csrf_token,
        },
        files={
            "hero_image_files": (
                "rename-me-before.png",
                b"\x89PNG\r\n\x1a\n" + b"2" * 16,
                "image/png",
            )
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.exec(select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)).first()
        assert hero_post is not None
        assert hero_post.content.startswith("/static/images/hero/")
        hero_post_id = hero_post.id

    posts_body = client.get("/admin/posts").text
    posts_csrf_token = _extract_csrf_token(posts_body)

    with Session(engine) as session:
        hero_post = session.get(Post, hero_post_id)
        assert hero_post is not None
        old_url = hero_post.content.strip()
        old_image_path = (
            Path(__file__).resolve().parents[1]
            / "app/static/images/hero"
            / old_url.removeprefix("/static/images/hero/")
        )
        assert old_image_path.exists()

    response = client.post(
        f"/admin/posts/{hero_post_id}/update",
        data={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": old_url,
            "is_published": "false",
            "csrf_token": posts_csrf_token,
            "hero_image_existing_urls": [old_url],
            "hero_image_filenames": ["renamed-hero.png"],
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.get(Post, hero_post_id)
        assert hero_post is not None
        assert hero_post.content == "/static/images/hero/renamed-hero.png"

    response = client.get("/")
    assert response.status_code == 200
    assert 'src="/static/images/hero/renamed-hero.png"' in response.text

    with Session(engine) as session:
        hero_post = session.get(Post, hero_post_id)
        assert hero_post is not None
        old_renamed_path = (
            Path(__file__).resolve().parents[1] / "app/static/images/hero/renamed-hero.png"
        )
        if old_image_path.exists():
            old_image_path.unlink()
        if old_renamed_path.exists():
            old_renamed_path.unlink()


def test_admin_posts_page_removes_missing_hero_image_paths(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}

    with Session(engine) as session:
        session.add(
            Post(
                title="홈 히어로 이미지",
                slug=HOME_HERO_IMAGE_POST_SLUG,
                content="/static/images/hero/not-exist.png",
                is_published=False,
            )
        )
        session.commit()

    _login_as_admin(app, cookie_jar)
    status_code, _, body = _request(app, "GET", "/admin/posts", cookies=cookie_jar)

    assert status_code == 200
    assert "/static/images/hero/hero.jpg" in body
    assert "/static/images/hero/not-exist.png" not in body

    with Session(engine) as session:
        hero_post = session.exec(select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)).first()
        assert hero_post is not None
        assert hero_post.content == "/static/images/hero/hero.jpg"


def test_admin_posts_page_keeps_existing_hero_image_and_removes_missing_one(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    hero_dir = Path(__file__).resolve().parents[1] / "app/static/images/hero"
    hero_dir.mkdir(parents=True, exist_ok=True)
    existing_file = hero_dir / "existing-sync-check.png"
    existing_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"8" * 16)

    try:
        with Session(engine) as session:
            session.add(
                Post(
                    title="홈 히어로 이미지",
                    slug=HOME_HERO_IMAGE_POST_SLUG,
                    content=(
                        "/static/images/hero/existing-sync-check.png\n"
                        "/static/images/hero/not-exist.png"
                    ),
                    is_published=False,
                )
            )
            session.commit()

        _login_as_admin(app, cookie_jar)
        status_code, _, body = _request(app, "GET", "/admin/posts", cookies=cookie_jar)

        assert status_code == 200
        assert "/static/images/hero/existing-sync-check.png" in body
        assert "/static/images/hero/not-exist.png" not in body

        with Session(engine) as session:
            hero_post = session.exec(
                select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)
            ).first()
            assert hero_post is not None
            assert hero_post.content == "/static/images/hero/existing-sync-check.png"
    finally:
        if existing_file.exists():
            existing_file.unlink()


def test_admin_posts_page_keeps_legacy_fallback_path_when_added(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}

    with Session(engine) as session:
        session.add(
            Post(
                title="홈 히어로 이미지",
                slug=HOME_HERO_IMAGE_POST_SLUG,
                content="/static/images/hero.jpg",
                is_published=False,
            )
        )
        session.commit()

    _login_as_admin(app, cookie_jar)
    status_code, _, body = _request(app, "GET", "/admin/posts", cookies=cookie_jar)

    assert status_code == 200
    assert "/static/images/hero/hero.jpg" in body
    assert "/static/images/hero.jpg" not in body

    with Session(engine) as session:
        hero_post = session.exec(select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)).first()
        assert hero_post is not None
        assert hero_post.content == "/static/images/hero/hero.jpg"


def test_home_hero_image_removal_helpers_filter_default_and_non_file_urls():
    removable_urls = admin_post._collect_removable_hero_image_urls(
        [
            "/static/images/hero/hero.jpg",
            "/static/images/hero/custom.png",
            "/static/other/image.jpg",
            "/images/hero/hero-banner.png",
            "https://external.example.com/a.png",
        ]
    )
    assert removable_urls == {
        "/static/images/hero/custom.png",
        "/static/images/hero/hero-banner.png",
    }


def test_home_hero_image_rename_rejects_default_path():
    renamed_urls, rename_map, error = admin_post._rename_hero_images(
        ["/static/images/hero/hero.jpg", "/static/images/hero/custom.png"],
        ["/static/images/hero/hero.jpg"],
        ["renamed.png"],
    )

    assert renamed_urls == []
    assert rename_map == {}
    assert error == "기본 히어로 이미지는 이름을 변경할 수 없습니다."


def test_home_hero_image_create_with_upload(app_and_engine):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app, engine = app_and_engine
    client = TestClient(app)

    login_body = client.get("/admin/login").text
    login_csrf_token = _extract_csrf_token(login_body)
    response = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "test-password",
            "csrf_token": login_csrf_token,
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"

    posts_body = client.get("/admin/posts").text
    posts_csrf_token = _extract_csrf_token(posts_body)

    response = client.post(
        "/admin/posts",
        data={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": "",
            "is_published": "false",
            "csrf_token": posts_csrf_token,
        },
        files={
            "hero_image_files": (
                "hero-upload-test.png",
                b"\x89PNG\r\n\x1a\n" + b"0" * 16,
                "image/png",
            )
        },
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.exec(select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)).first()
        assert hero_post is not None
        assert hero_post.content.startswith("/static/images/hero/")
        assert hero_post.content.endswith(".png")
        response = client.get("/")
        assert response.status_code == 200
        assert f'src="{hero_post.content}"' in response.text

        image_file_path = Path(__file__).resolve().parents[1] / "app/static/images/hero"
        for line in hero_post.content.splitlines():
            image_name = line.removeprefix("/static/images/hero/")
            file_path = image_file_path / image_name
            if file_path.exists():
                file_path.unlink()


def test_home_hero_image_delete_selected_image(app_and_engine):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app, engine = app_and_engine
    client = TestClient(app)

    login_body = client.get("/admin/login").text
    login_csrf_token = _extract_csrf_token(login_body)
    response = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "test-password",
            "csrf_token": login_csrf_token,
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"

    posts_body = client.get("/admin/posts").text
    posts_csrf_token = _extract_csrf_token(posts_body)

    response = client.post(
        "/admin/posts",
        data={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": "",
            "is_published": "false",
            "csrf_token": posts_csrf_token,
        },
        files={
            "hero_image_files": (
                "delete-me-first.png",
                b"\x89PNG\r\n\x1a\n" + b"1" * 16,
                "image/png",
            )
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.exec(select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)).first()
        assert hero_post is not None
        hero_post_id = hero_post.id
        first_image_url = hero_post.content.strip()

    assert first_image_url == "/static/images/hero/delete-me-first.png"

    posts_body = client.get("/admin/posts").text
    posts_csrf_token = _extract_csrf_token(posts_body)

    response = client.post(
        f"/admin/posts/{hero_post_id}/update",
        data={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": first_image_url,
            "is_published": "false",
            "csrf_token": posts_csrf_token,
        },
        files={
            "hero_image_files": (
                "delete-me-second.png",
                b"\x89PNG\r\n\x1a\n" + b"2" * 16,
                "image/png",
            )
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.exec(select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)).first()
        assert hero_post is not None
        hero_urls = [line for line in hero_post.content.splitlines() if line.strip()]
        assert len(hero_urls) == 2
        assert "/static/images/hero/delete-me-first.png" in hero_urls
        assert "/static/images/hero/delete-me-second.png" in hero_urls

    posts_body = client.get("/admin/posts").text
    posts_csrf_token = _extract_csrf_token(posts_body)

    response = client.post(
        f"/admin/posts/{hero_post_id}/update",
        data={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": first_image_url,
            "is_published": "false",
            "csrf_token": posts_csrf_token,
            "hero_image_remove_urls": "/static/images/hero/delete-me-first.png",
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.get(Post, hero_post_id)
        assert hero_post is not None
        hero_urls = [line for line in hero_post.content.splitlines() if line.strip()]
        assert hero_urls == ["/static/images/hero/delete-me-second.png"]

        first_image_path = (
            Path(__file__).resolve().parents[1] / "app/static/images/hero" / "delete-me-first.png"
        )
        second_image_path = (
            Path(__file__).resolve().parents[1] / "app/static/images/hero" / "delete-me-second.png"
        )
        assert not first_image_path.exists()
        assert second_image_path.exists()

        if second_image_path.exists():
            second_image_path.unlink()


def test_home_hero_image_delete_all_images_uses_fallback(app_and_engine):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    app, engine = app_and_engine
    client = TestClient(app)

    login_body = client.get("/admin/login").text
    login_csrf_token = _extract_csrf_token(login_body)
    response = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "test-password",
            "csrf_token": login_csrf_token,
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"

    posts_body = client.get("/admin/posts").text
    posts_csrf_token = _extract_csrf_token(posts_body)

    response = client.post(
        "/admin/posts",
        data={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": "",
            "is_published": "false",
            "csrf_token": posts_csrf_token,
        },
        files={
            "hero_image_files": (
                "delete-all.png",
                b"\x89PNG\r\n\x1a\n" + b"3" * 16,
                "image/png",
            )
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.exec(select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)).first()
        assert hero_post is not None
        hero_post_id = hero_post.id
        image_url = hero_post.content.strip()

    posts_body = client.get("/admin/posts").text
    posts_csrf_token = _extract_csrf_token(posts_body)

    response = client.post(
        f"/admin/posts/{hero_post_id}/update",
        data={
            "title": "홈 히어로 이미지",
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": image_url,
            "is_published": "false",
            "csrf_token": posts_csrf_token,
            "hero_image_remove_urls": image_url,
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.get(Post, hero_post_id)
        assert hero_post is not None
        assert hero_post.content == "/static/images/hero/hero.jpg"

    home_body = client.get("/")
    assert home_body.status_code == 200
    assert 'src="/static/images/hero/hero.jpg"' in home_body.text


def test_post_create_rejects_invalid_csrf(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    _ = _get_csrf_token(app, cookie_jar, "/admin/posts")

    status_code, _, _ = _request(
        app,
        "POST",
        "/admin/posts",
        form={
            "title": "Blocked Post",
            "slug": "blocked-post",
            "content": "blocked",
            "is_published": "true",
            "csrf_token": "invalid-token",
        },
        cookies=cookie_jar,
    )

    assert status_code == 403
    with Session(engine) as session:
        assert session.exec(select(Post)).all() == []

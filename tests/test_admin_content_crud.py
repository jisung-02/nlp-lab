"""Project, publication, and post CRUD integration tests."""

from __future__ import annotations

import asyncio
import re
from datetime import date
from http.cookies import SimpleCookie
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
            "slug": "nlp-platform",
            "summary": "초기 요약",
            "description": "프로젝트 상세 설명",
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
            "slug": "nlp-platform-v2",
            "summary": "수정 요약",
            "description": "수정된 설명",
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
        assert updated_project.slug == "nlp-platform-v2"
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
            "authors": "Author A, Author B",
            "venue": "ACL",
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
            "authors": "Author A",
            "venue": "EMNLP",
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
        assert updated_publication.venue == "EMNLP"
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
            "slug": "notice-1",
            "content": "초기 공지 내용",
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
            "slug": "notice-1-updated",
            "content": "수정 공지 내용",
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
            "content": "/static/images/hero-new.jpg",
            "is_published": "false",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/posts"

    with Session(engine) as session:
        hero_post = session.exec(
            select(Post).where(Post.slug == HOME_HERO_IMAGE_POST_SLUG)
        ).first()
        assert hero_post is not None
        assert hero_post.content == "/static/images/hero-new.jpg"
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
            "content": "/static/images/hero-updated.jpg",
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
        assert updated_hero_post.content == "/static/images/hero-updated.jpg"
        assert updated_hero_post.is_published is False

    status_code, _, body = _request(app, "GET", "/")
    assert status_code == 200
    assert 'src="/static/images/hero-updated.jpg"' in body


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

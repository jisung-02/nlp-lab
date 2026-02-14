from __future__ import annotations

import asyncio
import re
from datetime import date
from http.cookies import SimpleCookie
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from starlette.types import Message, Receive, Scope, Send

from app.core.constants import MemberRole, ProjectStatus
from app.core.security import hash_password
from app.db.session import get_session
from app.main import create_app
from app.models.admin_user import AdminUser
from app.models.member import Member
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


def test_unauthenticated_admin_access_redirects_to_login(app_and_engine):
    app, _ = app_and_engine

    status_code, headers, _ = _request(app, "GET", "/admin")

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/login"


def test_login_page_sets_session_cookie_with_required_options(app_and_engine):
    app, _ = app_and_engine

    status_code, headers, _ = _request(app, "GET", "/admin/login")
    session_cookie = _header_value(headers, "set-cookie")

    assert status_code == 200
    assert session_cookie is not None
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie


def test_login_success_allows_dashboard_and_logout_blocks_later_access(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}

    with Session(engine) as session:
        session.add(
            Member(
                name="member-1",
                role=MemberRole.RESEARCHER,
                email="member-1@example.com",
                display_order=1,
            )
        )
        session.add(
            Project(
                title="project-1",
                slug="project-1",
                summary="summary",
                description="description",
                status=ProjectStatus.ONGOING,
                start_date=date(2025, 1, 1),
            )
        )
        session.add(
            Publication(
                title="publication-1",
                authors="author-1",
                venue="venue-1",
                year=2025,
            )
        )
        session.add(
            Post(
                title="post-1",
                slug="post-1",
                content="content-1",
                is_published=True,
            )
        )
        session.commit()

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

    status_code, _, dashboard_body = _request(app, "GET", "/admin", cookies=cookie_jar)
    dashboard_csrf_token = _extract_csrf_token(dashboard_body)

    assert status_code == 200
    assert "멤버 수: 1" in dashboard_body
    assert "프로젝트 수: 1" in dashboard_body
    assert "논문 수: 1" in dashboard_body
    assert "게시글 수: 1" in dashboard_body

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/logout",
        form={"csrf_token": dashboard_csrf_token},
        cookies=cookie_jar,
    )
    _update_cookie_jar(cookie_jar, headers)

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/login"

    status_code, headers, _ = _request(app, "GET", "/admin", cookies=cookie_jar)

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/login"


def test_authenticated_admin_pages_render(app_and_engine):
    app, _ = app_and_engine
    cookie_jar: dict[str, str] = {}

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

    for route in [
        "/admin",
        "/admin/members",
        "/admin/projects",
        "/admin/publications",
        "/admin/posts",
    ]:
        status_code, headers, _ = _request(app, "GET", route, cookies=cookie_jar)
        _update_cookie_jar(cookie_jar, headers)
        assert status_code == 200


def test_login_rejects_csrf_mismatch(app_and_engine):
    app, _ = app_and_engine
    cookie_jar: dict[str, str] = {}

    status_code, headers, _ = _request(app, "GET", "/admin/login")
    _update_cookie_jar(cookie_jar, headers)

    assert status_code == 200

    status_code, _, _ = _request(
        app,
        "POST",
        "/admin/login",
        form={
            "username": "admin",
            "password": "test-password",
            "csrf_token": "invalid-token",
        },
        cookies=cookie_jar,
    )

    assert status_code == 403


def test_login_rejects_missing_csrf(app_and_engine):
    app, _ = app_and_engine
    cookie_jar: dict[str, str] = {}

    status_code, headers, _ = _request(app, "GET", "/admin/login")
    _update_cookie_jar(cookie_jar, headers)

    assert status_code == 200

    status_code, _, _ = _request(
        app,
        "POST",
        "/admin/login",
        form={
            "username": "admin",
            "password": "test-password",
        },
        cookies=cookie_jar,
    )

    assert status_code == 422

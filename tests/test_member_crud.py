"""Member CRUD integration tests."""

from __future__ import annotations

import asyncio
import re
from http.cookies import SimpleCookie
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from starlette.types import Message, Receive, Scope, Send

from app.core.constants import MemberRole
from app.core.security import hash_password
from app.db.session import get_session
from app.main import create_app
from app.models.admin_user import AdminUser
from app.models.member import Member


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


def _get_members_csrf_token(app: FastAPI, cookie_jar: dict[str, str]) -> str:
    status_code, headers, body = _request(app, "GET", "/admin/members", cookies=cookie_jar)
    _update_cookie_jar(cookie_jar, headers)
    assert status_code == 200
    return _extract_csrf_token(body)


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


def test_member_create_update_delete_flow(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_members_csrf_token(app, cookie_jar)

    status_code, headers, _ = _request(
        app,
        "POST",
        "/admin/members",
        form={
            "name": "홍길동",
            "role": "researcher",
            "email": "member@example.com",
            "photo_url": "https://example.com/profile.jpg",
            "bio": "초기 소개",
            "display_order": "10",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/members"

    with Session(engine) as session:
        member = session.exec(
            select(Member).where(Member.email == "member@example.com")
        ).first()
        assert member is not None
        assert member.name == "홍길동"
        assert member.role == MemberRole.RESEARCHER
        member_id = member.id

    assert member_id is not None
    csrf_token = _get_members_csrf_token(app, cookie_jar)

    status_code, headers, _ = _request(
        app,
        "POST",
        f"/admin/members/{member_id}/update",
        form={
            "name": "김연구",
            "role": "phd",
            "email": "member-updated@example.com",
            "photo_url": "https://example.com/new.jpg",
            "bio": "수정 소개",
            "display_order": "2",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/members"

    with Session(engine) as session:
        updated_member = session.get(Member, member_id)
        assert updated_member is not None
        assert updated_member.name == "김연구"
        assert updated_member.role == MemberRole.PHD
        assert updated_member.email == "member-updated@example.com"
        assert updated_member.display_order == 2

    csrf_token = _get_members_csrf_token(app, cookie_jar)
    status_code, headers, _ = _request(
        app,
        "POST",
        f"/admin/members/{member_id}/delete",
        form={"csrf_token": csrf_token},
        cookies=cookie_jar,
    )

    assert status_code == 303
    assert _header_value(headers, "location") == "/admin/members"

    with Session(engine) as session:
        assert session.get(Member, member_id) is None


def test_member_create_rejects_duplicate_email_and_invalid_payload(app_and_engine):
    app, engine = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_members_csrf_token(app, cookie_jar)

    status_code, _, _ = _request(
        app,
        "POST",
        "/admin/members",
        form={
            "name": "멤버 A",
            "role": "researcher",
            "email": "duplicate@example.com",
            "display_order": "1",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )
    assert status_code == 303

    csrf_token = _get_members_csrf_token(app, cookie_jar)
    status_code, _, duplicate_body = _request(
        app,
        "POST",
        "/admin/members",
        form={
            "name": "멤버 B",
            "role": "phd",
            "email": "duplicate@example.com",
            "display_order": "2",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 400
    assert "이미 사용 중인 이메일입니다." in duplicate_body

    csrf_token = _extract_csrf_token(duplicate_body)
    status_code, _, invalid_body = _request(
        app,
        "POST",
        "/admin/members",
        form={
            "name": "멤버 C",
            "role": "invalid-role",
            "email": "new@example.com",
            "display_order": "3",
            "csrf_token": csrf_token,
        },
        cookies=cookie_jar,
    )

    assert status_code == 400
    assert "멤버 입력값을 확인해주세요." in invalid_body

    with Session(engine) as session:
        members = session.exec(select(Member)).all()
    assert len(members) == 1


def test_member_routes_reject_invalid_csrf_and_missing_delete_target(app_and_engine):
    app, _ = app_and_engine
    cookie_jar: dict[str, str] = {}
    _login_as_admin(app, cookie_jar)
    csrf_token = _get_members_csrf_token(app, cookie_jar)

    status_code, _, _ = _request(
        app,
        "POST",
        "/admin/members",
        form={
            "name": "멤버 X",
            "role": "researcher",
            "email": "memberx@example.com",
            "display_order": "1",
            "csrf_token": "invalid-token",
        },
        cookies=cookie_jar,
    )
    assert status_code == 403

    status_code, _, body = _request(
        app,
        "POST",
        "/admin/members/999/delete",
        form={"csrf_token": csrf_token},
        cookies=cookie_jar,
    )
    assert status_code == 404
    assert "멤버를 찾을 수 없습니다." in body

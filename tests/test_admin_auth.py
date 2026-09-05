from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import Session

from app.core.config import get_settings
from app.core.constants import MemberRole, ProjectStatus
from app.core.security import hash_password
from app.main import create_app
from app.models.admin_user import AdminUser
from app.models.member import Member
from app.models.post import Post
from app.models.project import Project
from app.models.publication import Publication
from tests.helpers import extract_csrf_token as _extract_csrf_token
from tests.helpers import header_value as _header_value
from tests.helpers import request as _request
from tests.helpers import update_cookie_jar as _update_cookie_jar


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
    assert "Max-Age=" in session_cookie
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie


def test_login_page_sets_secure_session_cookie_in_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "test-key-" * 8)
    monkeypatch.setenv("ADMIN_PASSWORD", "a-real-test-password")
    get_settings.cache_clear()
    app = create_app()

    try:
        status_code, headers, _ = _request(app, "GET", "/admin/login")
    finally:
        get_settings.cache_clear()

    session_cookie = _header_value(headers, "set-cookie")

    assert status_code == 200
    assert session_cookie is not None
    assert "Secure" in session_cookie


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


def _login_cookies(app):
    from fastapi.testclient import TestClient

    client = TestClient(app, follow_redirects=False)
    token = _extract_csrf_token(client.get("/admin/login").text)
    assert (
        client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "test-password",
                "csrf_token": token,
            },
        ).status_code
        == 303
    )
    return client


def test_old_cookie_is_rejected_after_logout_expiry_password_change_and_account_deletion(
    app_and_engine,
):
    from sqlmodel import select

    from app.models.admin_session import AdminSession

    app, engine = app_and_engine
    client = _login_cookies(app)
    stolen = client.cookies.get("nlp_lab_session")
    token = _extract_csrf_token(client.get("/admin").text)
    assert client.post("/admin/logout", data={"csrf_token": token}).status_code == 303
    assert client.get("/admin", headers={"Cookie": f"nlp_lab_session={stolen}"}).status_code == 303

    for change in ("expiry", "password", "delete"):
        client = _login_cookies(app)
        with Session(engine) as session:
            if change == "expiry":
                for login_session in session.exec(select(AdminSession)).all():
                    login_session.expires_at = 0
                    session.add(login_session)
            else:
                admin = session.exec(select(AdminUser)).one()
                if change == "password":
                    admin.password_hash = hash_password("test-password")
                    session.add(admin)
                else:
                    session.delete(admin)
            session.commit()
        for path in (
            "/admin",
            "/admin/members",
            "/admin/projects",
            "/admin/publications",
            "/admin/posts",
        ):
            assert client.get(path).status_code == 303


def test_production_rejects_default_credentials():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(app_env="production")
    with pytest.raises(ValidationError):
        Settings(app_env="production", secret_key="x" * 32)
    Settings(app_env="production", secret_key="x" * 32, admin_password="custom")


def test_expired_signed_cookie_and_missing_admin_cannot_authenticate(app_and_engine):
    import time

    from app.services.auth_service import decode_session_cookie, encode_session_cookie

    secret = get_settings().secret_key
    cookie = encode_session_cookie(secret, {"admin_user_id": 1, "expires_at": int(time.time()) - 1})
    assert decode_session_cookie(secret, cookie) == {}
    app, _ = app_and_engine
    cookie = encode_session_cookie(secret, {"admin_user_id": 999999})
    status, _, _ = _request(app, "GET", "/admin", cookies={"nlp_lab_session": cookie})
    assert status == 303

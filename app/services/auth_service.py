"""Authentication and CSRF helper services."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from hmac import compare_digest
from typing import Any

from fastapi import Request
from pydantic import ValidationError
from sqlmodel import Session, col, select

from app.core.security import verify_password
from app.models.admin_user import AdminUser
from app.schemas.auth import AdminLoginInput, CsrfInput

SESSION_ADMIN_USER_ID_KEY = "admin_user_id"
SESSION_CSRF_TOKEN_KEY = "csrf_token"


def decode_session_cookie(secret_key: str, raw_cookie: str | None) -> dict[str, Any]:
    """Decode and validate signed session cookie payload."""

    if raw_cookie is None or "." not in raw_cookie:
        return {}
    encoded_payload, signature = raw_cookie.rsplit(".", 1)
    if not compare_digest(_sign_payload(secret_key, encoded_payload), signature):
        return {}
    try:
        padding = "=" * (-len(encoded_payload) % 4)
        payload = base64.urlsafe_b64decode(f"{encoded_payload}{padding}".encode())
        data = json.loads(payload.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items()}


def encode_session_cookie(secret_key: str, session_data: dict[str, Any]) -> str:
    """Encode session dict and sign it for cookie storage."""

    raw_payload = json.dumps(session_data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(raw_payload).decode("utf-8").rstrip("=")
    signature = _sign_payload(secret_key, encoded_payload)
    return f"{encoded_payload}.{signature}"


def parse_login_input(username: str, password: str, csrf_token: str) -> AdminLoginInput | None:
    """Return validated login input or ``None`` for invalid payload."""

    try:
        return AdminLoginInput(username=username, password=password, csrf_token=csrf_token)
    except ValidationError:
        return None


def parse_csrf_input(csrf_token: str) -> CsrfInput | None:
    """Return validated CSRF input or ``None`` for invalid payload."""

    try:
        return CsrfInput(csrf_token=csrf_token)
    except ValidationError:
        return None


def authenticate_admin(session: Session, username: str, password: str) -> AdminUser | None:
    """Authenticate an admin account by username and password."""

    admin_user = session.exec(select(AdminUser).where(col(AdminUser.username) == username)).first()
    if admin_user is None:
        return None
    if not verify_password(password, admin_user.password_hash):
        return None
    return admin_user


def get_authenticated_admin(request: Request, session: Session) -> AdminUser | None:
    """Return the currently authenticated admin from session."""

    admin_user_id = request.session.get(SESSION_ADMIN_USER_ID_KEY)
    if not isinstance(admin_user_id, int):
        return None
    return session.get(AdminUser, admin_user_id)


def login_admin(request: Request, admin_user: AdminUser) -> None:
    """Persist admin login state in session."""

    request.session[SESSION_ADMIN_USER_ID_KEY] = admin_user.id
    rotate_csrf_token(request)


def logout_admin(request: Request) -> None:
    """Clear the session for logout."""

    request.session.clear()


def get_or_create_csrf_token(request: Request) -> str:
    """Return existing CSRF token or issue a new one."""

    csrf_token = request.session.get(SESSION_CSRF_TOKEN_KEY)
    if isinstance(csrf_token, str) and csrf_token:
        return csrf_token
    return rotate_csrf_token(request)


def rotate_csrf_token(request: Request) -> str:
    """Generate and store a fresh CSRF token."""

    csrf_token = secrets.token_urlsafe(32)
    request.session[SESSION_CSRF_TOKEN_KEY] = csrf_token
    return csrf_token


def validate_csrf_token(request: Request, csrf_token: str) -> bool:
    """Return whether submitted CSRF token matches server token."""

    validated_input = parse_csrf_input(csrf_token)
    if validated_input is None:
        return False
    session_token = request.session.get(SESSION_CSRF_TOKEN_KEY)
    if not isinstance(session_token, str) or not session_token:
        return False
    return compare_digest(session_token, validated_input.csrf_token)


def _sign_payload(secret_key: str, payload: str) -> str:
    digest = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()

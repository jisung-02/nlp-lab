"""Authentication and CSRF helper services."""

from __future__ import annotations

import secrets
from hmac import compare_digest

from fastapi import Request
from pydantic import ValidationError
from sqlmodel import Session, col, select

from app.core.security import verify_password
from app.models.admin_user import AdminUser
from app.schemas.auth import AdminLoginInput, CsrfInput

SESSION_ADMIN_USER_ID_KEY = "admin_user_id"
SESSION_CSRF_TOKEN_KEY = "csrf_token"


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

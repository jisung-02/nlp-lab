import base64
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.routers.admin_auth import router as admin_auth_router
from app.routers.admin_member import router as admin_member_router
from app.routers.admin_post import router as admin_post_router
from app.routers.admin_project import router as admin_project_router
from app.routers.admin_publication import router as admin_publication_router
from app.routers.public import router as public_router
from app.services.auth_service import SESSION_ADMIN_USER_ID_KEY

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
SESSION_COOKIE_NAME = "nlp_lab_session"


def _is_admin_path(path: str) -> bool:
    return path == "/admin" or path.startswith("/admin/")


def _is_login_path(path: str) -> bool:
    return path == "/admin/login" or path.startswith("/admin/login/")


def _sign_payload(secret_key: str, payload: str) -> str:
    digest = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def _encode_session(secret_key: str, session_data: dict[str, Any]) -> str:
    raw_payload = json.dumps(session_data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(raw_payload).decode("utf-8").rstrip("=")
    signature = _sign_payload(secret_key, encoded_payload)
    return f"{encoded_payload}.{signature}"


def _decode_session(secret_key: str, raw_cookie: str | None) -> dict[str, Any]:
    if raw_cookie is None or "." not in raw_cookie:
        return {}
    encoded_payload, signature = raw_cookie.rsplit(".", 1)
    if not hmac.compare_digest(_sign_payload(secret_key, encoded_payload), signature):
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


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.app_debug)

    @app.middleware("http")
    async def session_and_admin_guard(request: Request, call_next):
        request.scope["session"] = _decode_session(
            settings.secret_key,
            request.cookies.get(SESSION_COOKIE_NAME),
        )

        path = request.url.path
        if _is_admin_path(path) and not _is_login_path(path):
            if not isinstance(request.session.get(SESSION_ADMIN_USER_ID_KEY), int):
                return RedirectResponse(url="/admin/login", status_code=303)

        response = await call_next(request)
        session_data = request.scope.get("session")
        if isinstance(session_data, dict) and session_data:
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=_encode_session(settings.secret_key, session_data),
                httponly=True,
                samesite="lax",
                secure=settings.is_production,
                path="/",
            )
        else:
            response.delete_cookie(
                key=SESSION_COOKIE_NAME,
                httponly=True,
                samesite="lax",
                secure=settings.is_production,
                path="/",
            )
        return response

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.include_router(public_router)
    app.include_router(admin_auth_router)
    app.include_router(admin_member_router)
    app.include_router(admin_project_router)
    app.include_router(admin_publication_router)
    app.include_router(admin_post_router)
    return app


app = create_app()

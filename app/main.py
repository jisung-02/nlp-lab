from pathlib import Path

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
from app.services.auth_service import (
    SESSION_ADMIN_USER_ID_KEY,
    decode_session_cookie,
    encode_session_cookie,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
SESSION_COOKIE_NAME = "nlp_lab_session"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.app_debug)

    @app.middleware("http")
    async def session_and_admin_guard(request: Request, call_next):
        request.scope["session"] = decode_session_cookie(
            settings.secret_key,
            request.cookies.get(SESSION_COOKIE_NAME),
        )

        path = request.url.path
        is_admin_path = path == "/admin" or path.startswith("/admin/")
        is_login_path = path == "/admin/login" or path.startswith("/admin/login/")
        if is_admin_path and not is_login_path:
            if not isinstance(request.session.get(SESSION_ADMIN_USER_ID_KEY), int):
                return RedirectResponse(url="/admin/login", status_code=303)

        response = await call_next(request)
        session_data = request.scope.get("session")
        if isinstance(session_data, dict) and session_data:
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=encode_session_cookie(settings.secret_key, session_data),
                max_age=settings.admin_session_max_age_seconds,
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

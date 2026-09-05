from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

from app.core.config import get_settings
from app.core.static_assets import STATIC_URL_PREFIX, static_url
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
    require_admin,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
SESSION_COOKIE_NAME = "nlp_lab_session"


class CachedStaticFiles(StaticFiles):
    """Serves /static with cache lifetimes that match how each URL is used.

    Repository assets are linked via ``static_url`` with a content-hash
    ``v`` query parameter, so their URL changes whenever the file does and
    they can be cached for a year as immutable.

    Uploaded files keep their original filename instead of a content
    hash, so an admin replacing an image can reuse the same URL. A long
    "immutable" cache would then serve stale bytes; a 1-hour window with
    revalidation keeps repeat page loads fast without that risk.
    """

    def file_response(self, full_path, stat_result, scope, status_code=200):
        response = super().file_response(full_path, stat_result, scope, status_code)
        if _is_versioned_request(scope):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"
        return response


def _is_versioned_request(scope) -> bool:
    query_string = scope.get("query_string", b"")
    return query_string.startswith(b"v=") or b"&v=" in query_string


def _is_static_path(path: str) -> bool:
    return path == STATIC_URL_PREFIX or path.startswith(f"{STATIC_URL_PREFIX}/")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.app_debug)
    app.add_middleware(GZipMiddleware, minimum_size=1024)  # ty: ignore[invalid-argument-type]

    @app.middleware("http")
    async def session_and_admin_guard(request: Request, call_next):
        path = request.url.path
        if _is_static_path(path):
            # Static files never read the session. Skipping the cookie
            # round-trip here also keeps Set-Cookie off static responses,
            # which shared caches and CDNs refuse to store otherwise.
            return await call_next(request)

        raw_session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        request.scope["session"] = decode_session_cookie(settings.secret_key, raw_session_cookie)

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
        elif raw_session_cookie is not None:
            # Only public visitors reach here without a cookie; clearing a
            # cookie they never had would just bloat every response.
            response.delete_cookie(
                key=SESSION_COOKIE_NAME,
                httponly=True,
                samesite="lax",
                secure=settings.is_production,
                path="/",
            )
        return response

    app.mount("/static", CachedStaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    # Compiled templates are cached by Jinja; in production skip the
    # per-render mtime check on every template file as well.
    templates.env.auto_reload = not settings.is_production
    templates.env.globals["static_url"] = static_url
    app.state.templates = templates
    app.include_router(public_router)
    app.include_router(admin_auth_router)
    app.include_router(admin_member_router, dependencies=[Depends(require_admin)])
    app.include_router(admin_project_router, dependencies=[Depends(require_admin)])
    app.include_router(admin_publication_router, dependencies=[Depends(require_admin)])
    app.include_router(admin_post_router, dependencies=[Depends(require_admin)])
    return app


app = create_app()

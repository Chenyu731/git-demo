import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth
from .config import check_startup_safety, get_settings
from .routers import admin, internal, public

BASE = Path(__file__).parent


def create_app() -> FastAPI:
    s = get_settings()
    check_startup_safety(s)
    app = FastAPI(title="分機通訊錄", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SessionMiddleware, secret_key=s.session_secret, session_cookie=s.session_cookie,
                       https_only=s.app_env == "production", same_site="lax", max_age=8 * 3600)
    app.state.templates = Jinja2Templates(directory=str(BASE / "templates"))
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    app.include_router(public.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(internal.router)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.exception_handler(HTTPException)
    async def http_exc(request: Request, exc: HTTPException):
        # 瀏覽器開維護頁沒登入 → 導向登入；API 呼叫端拿 JSON
        if exc.status_code == 401 and request.url.path.startswith("/admin"):
            return RedirectResponse("/auth/login", status_code=303)
        if exc.status_code in (403, 404) and "text/html" in request.headers.get("accept", ""):
            return app.state.templates.TemplateResponse(request, "error.html", {"code": exc.status_code, "detail": exc.detail},
                                                        status_code=exc.status_code)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    logging.basicConfig(level=logging.INFO)
    return app


app = create_app()

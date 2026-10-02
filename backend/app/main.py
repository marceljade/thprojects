from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, database
from .routers.api import router
from .migrate import migrate
from .seed import seed
from .services import outlook
from .services.admin import daily_backup_if_due


def create_app(database_url: str | None = None, serve_static: bool = True) -> FastAPI:
    config.ensure_dirs()
    database.init_engine(database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        from . import models  # noqa: F401 – Tabellen registrieren
        added = migrate(database.engine)
        if added:
            print("Datenbank ergänzt um:", ", ".join(added))
        outlook.register(database.SessionLocal)
        with database.SessionLocal() as db:
            seed(db)
            daily_backup_if_due(db)
            outlook.start_auto_on_boot(db)
        yield

    app = FastAPI(title=config.APP_NAME, version=config.VERSION, lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(HTTPException)
    async def _http_error(_request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    if serve_static and config.STATIC_DIR.is_dir():
        assets = config.STATIC_DIR / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            candidate = config.STATIC_DIR / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(config.STATIC_DIR / "index.html")

    return app


app = create_app()

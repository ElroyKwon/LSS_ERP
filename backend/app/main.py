from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
import os
import traceback

from dotenv import load_dotenv
load_dotenv()

from .config import settings
from .database import engine, Base
from .models import *  # noqa: register all models
from .utils.authorization import enforce_api_permissions
from .utils.schema import ensure_accounting_columns, ensure_execution_columns, ensure_master_columns

from .routers import auth, master, sales, forecast, execution, management, timesheet, vehicle, opinion, holiday, schedule, ai

# Development convenience. Production deployments should run Alembic migrations
# and set AUTO_CREATE_SCHEMA=false to keep schema changes explicit.
if settings.AUTO_CREATE_SCHEMA:
    Base.metadata.create_all(bind=engine)
    ensure_master_columns(engine)
    ensure_accounting_columns(engine)
    ensure_execution_columns(engine)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs" if settings.API_DOCS_ENABLED else None,
    redoc_url="/api/redoc" if settings.API_DOCS_ENABLED else None,
    openapi_url="/api/openapi.json" if settings.API_DOCS_ENABLED else None,
)

if settings.is_production_like:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.hosts,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(enforce_api_permissions)

app.include_router(auth.router)
app.include_router(master.router)
app.include_router(sales.router)
app.include_router(forecast.router)
app.include_router(execution.router)
app.include_router(management.router)
app.include_router(timesheet.router)
app.include_router(vehicle.router)
app.include_router(opinion.router)
app.include_router(holiday.router)
app.include_router(schedule.router)
app.include_router(ai.router)



# 프론트엔드 정적 파일 서빙
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            fallback = self._find_current_hashed_asset(path)
            if not fallback:
                raise
            response = FileResponse(fallback)
        response.headers["Cache-Control"] = "no-store"
        return response

    def _find_current_hashed_asset(self, path):
        name = os.path.basename(path)
        stem, ext = os.path.splitext(name)
        if "-" not in stem or not ext:
            return None
        chunk_name = stem.rsplit("-", 1)[0]
        try:
            candidates = [
                os.path.join(self.directory, f)
                for f in os.listdir(self.directory)
                if f.startswith(f"{chunk_name}-") and f.endswith(ext)
            ]
        except OSError:
            return None
        if not candidates:
            return None
        return max(candidates, key=os.path.getmtime)


if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", NoCacheStaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path, headers={"Cache-Control": "no-store"})
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"), headers={"Cache-Control": "no-store"})

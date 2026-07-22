import asyncio
from datetime import datetime, timedelta

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
from .database import engine, Base, SessionLocal
from .models import *  # noqa: register all models
from .utils.authorization import enforce_api_permissions
from .services.holiday_sync import list_holidays, sync_holidays_for_year
from .utils.schema import (
    ensure_accounting_columns,
    ensure_calendar_schedule_tables,
    ensure_execution_columns,
    ensure_master_columns,
    ensure_management_columns,
    ensure_project_column_types,
    ensure_security_tables,
)

from .routers import auth, master, sales, forecast, execution, management, timesheet, vehicle, opinion, holiday, schedule, ai

# Development convenience. Production deployments should run Alembic migrations
# and set AUTO_CREATE_SCHEMA=false to keep schema changes explicit.
if settings.AUTO_CREATE_SCHEMA:
    Base.metadata.create_all(bind=engine)
    ensure_master_columns(engine)
    ensure_accounting_columns(engine)
    ensure_execution_columns(engine)
ensure_security_tables(engine)
ensure_calendar_schedule_tables(engine)
ensure_project_column_types(engine)
ensure_management_columns(engine)

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

def _seconds_until_next_sunday(hour: int = 3) -> float:
    now = datetime.now()
    days_until_sunday = (6 - now.weekday()) % 7
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
    if target <= now:
        target += timedelta(days=7)
    return max((target - now).total_seconds(), 60.0)


async def _sync_holidays_if_empty(year: str) -> None:
    db = SessionLocal()
    try:
        if not list_holidays(db, year):
            await sync_holidays_for_year(db, year)
    except Exception as exc:
        print(f"怨듯쑕??珥덇린 ?숆린???ㅽ뙣({year}): {exc}")
    finally:
        db.close()


async def _holiday_weekly_sync_loop() -> None:
    while True:
        await asyncio.sleep(_seconds_until_next_sunday())
        year = datetime.now().strftime("%Y")
        db = SessionLocal()
        try:
            await sync_holidays_for_year(db, year)
        except Exception as exc:
            print(f"怨듯쑕??二쇨컙 ?숆린???ㅽ뙣({year}): {exc}")
        finally:
            db.close()


@app.on_event("startup")
async def start_holiday_weekly_sync() -> None:
    await _sync_holidays_if_empty(datetime.now().strftime("%Y"))
    asyncio.create_task(_holiday_weekly_sync_loop())

# ?袁⑥쨴?紐꾨퓦???類ㅼ읅 ???뵬 ??뺥뒅
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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .config import settings
from .database import engine, Base
from .models import *  # noqa: register all models
from .utils.schema import ensure_master_columns

from .routers import auth, master, sales, purchase, accounting, forecast, budget, execution, management, timesheet, vehicle

Base.metadata.create_all(bind=engine)
ensure_master_columns(engine)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs" if settings.API_DOCS_ENABLED else None,
    redoc_url="/api/redoc" if settings.API_DOCS_ENABLED else None,
    openapi_url="/api/openapi.json" if settings.API_DOCS_ENABLED else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(master.router)
app.include_router(sales.router)
app.include_router(purchase.router)
app.include_router(accounting.router)
app.include_router(forecast.router)
app.include_router(budget.router)
app.include_router(execution.router)
app.include_router(management.router)
app.include_router(timesheet.router)
app.include_router(vehicle.router)

# 프론트엔드 정적 파일 서빙
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", NoCacheStaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path, headers={"Cache-Control": "no-store"})
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"), headers={"Cache-Control": "no-store"})

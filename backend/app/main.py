import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from .config import get_settings
from .db import engine, init_db
from .auto_import import recover_interrupted_import
from .routers import auth_routes, items, requests_routes, masterdata, accounting, admin, ai, catalogs

settings=get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.init_db_on_startup:
        init_db()
    try:
        recover_interrupted_import()
    except Exception:
        logging.getLogger(__name__).exception("Không thể kiểm tra trạng thái import bị gián đoạn")
    # Import/scheduler work intentionally runs only in ``python -m app.jobs``.
    # Web workers therefore never execute a long import after returning HTTP 202.
    yield

app=FastAPI(title=settings.app_name, version="1.7.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_routes.router); app.include_router(items.router); app.include_router(requests_routes.router); app.include_router(masterdata.router); app.include_router(accounting.router)
app.include_router(admin.router)
app.include_router(ai.router)
app.include_router(catalogs.router)

@app.get("/health")
def health(response: Response):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "service": settings.app_name, "database": "connected"}
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "service": settings.app_name, "database": "unavailable"}


@app.get("/health/live")
def live():
    return {"status": "ok", "service": settings.app_name}

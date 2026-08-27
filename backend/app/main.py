import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from .config import get_settings
from .db import engine, init_db
from .request_expiry import request_expiry_worker
from .auto_import import auto_import_worker
from .routers import auth_routes, items, requests_routes, masterdata, accounting, admin, ai, catalogs

settings=get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.init_db_on_startup:
        init_db()
    tasks = []
    if settings.run_background_jobs:
        tasks = [
            asyncio.create_task(request_expiry_worker()),
            asyncio.create_task(auto_import_worker()),
        ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                pass

app=FastAPI(title=settings.app_name, version="1.6.9", lifespan=lifespan)
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

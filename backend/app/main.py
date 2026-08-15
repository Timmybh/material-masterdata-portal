from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .db import init_db
from .routers import auth_routes, items, requests_routes, masterdata, accounting, admin, ai

settings=get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app=FastAPI(title=settings.app_name, version="1.6.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_routes.router); app.include_router(items.router); app.include_router(requests_routes.router); app.include_router(masterdata.router); app.include_router(accounting.router)
app.include_router(admin.router)
app.include_router(ai.router)

@app.get("/health")
def health(): return {"status":"ok","service":settings.app_name}

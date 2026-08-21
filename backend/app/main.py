import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .db import init_db
from .request_expiry import request_expiry_worker
from .auto_import import auto_import_worker
from .routers import auth_routes, items, requests_routes, masterdata, accounting, admin, ai, catalogs

settings=get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    expiry_task = asyncio.create_task(request_expiry_worker())
    import_task = asyncio.create_task(auto_import_worker())
    try:
        yield
    finally:
        expiry_task.cancel()
        import_task.cancel()
        try:
            await asyncio.gather(expiry_task, import_task)
        except asyncio.CancelledError:
            pass

app=FastAPI(title=settings.app_name, version="1.6.6", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_routes.router); app.include_router(items.router); app.include_router(requests_routes.router); app.include_router(masterdata.router); app.include_router(accounting.router)
app.include_router(admin.router)
app.include_router(ai.router)
app.include_router(catalogs.router)

@app.get("/health")
def health(): return {"status":"ok","service":settings.app_name}

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:12345678@db:5432/masterdata",
)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(
    title="Material Masterdata Portal API",
    version="1.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MaterialRequestCreate(BaseModel):
    proposed_name: str = Field(min_length=2, max_length=500)
    description: str | None = Field(default=None, max_length=4000)
    unit: str | None = Field(default=None, max_length=50)
    material_group: str | None = Field(default=None, max_length=100)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"

    return {
        "status": "ok" if database == "ok" else "degraded",
        "service": "material-masterdata-portal",
        "database": database,
        "version": "1.3.0",
    }


@app.get("/api/v1")
async def api_root():
    return {
        "name": "Material Masterdata Portal",
        "version": "1.3.0",
        "workflow": [
            "USER",
            "MASTERDATA",
            "ACCOUNTING",
            "COMPLETED",
        ],
    }


@app.get("/api/v1/materials/search")
async def search_materials(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
):
    keyword = q.strip()

    sql = text(
        """
        SELECT
            id,
            material_code,
            material_name,
            description,
            unit,
            material_group,
            created_at
        FROM materials
        WHERE
            :keyword = ''
            OR to_tsvector(
                'simple',
                coalesce(material_code, '') || ' ' ||
                coalesce(material_name, '') || ' ' ||
                coalesce(description, '')
            ) @@ plainto_tsquery('simple', :keyword)
            OR material_code ILIKE :pattern
            OR material_name ILIKE :pattern
            OR coalesce(description, '') ILIKE :pattern
        ORDER BY material_code
        LIMIT :limit
        """
    )

    async with engine.connect() as conn:
        result = await conn.execute(
            sql,
            {
                "keyword": keyword,
                "pattern": f"%{keyword}%",
                "limit": limit,
            },
        )
        rows = [dict(row) for row in result.mappings().all()]

    return {
        "query": keyword,
        "count": len(rows),
        "items": rows,
    }


@app.post("/api/v1/requests", status_code=201)
async def create_material_request(payload: MaterialRequestCreate):
    request_no = (
        f"REQ-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-"
        f"{uuid4().hex[:6].upper()}"
    )

    async with engine.begin() as conn:
        requester_result = await conn.execute(
            text("SELECT id FROM users WHERE email = :email LIMIT 1"),
            {"email": "user@example.com"},
        )
        requester_id = requester_result.scalar_one_or_none()

        if requester_id is None:
            raise HTTPException(status_code=500, detail="Demo requester not found")

        insert_result = await conn.execute(
            text(
                """
                INSERT INTO material_requests (
                    request_no,
                    requester_id,
                    proposed_name,
                    description,
                    unit,
                    material_group,
                    status
                )
                VALUES (
                    :request_no,
                    :requester_id,
                    :proposed_name,
                    :description,
                    :unit,
                    :material_group,
                    'PENDING_MASTERDATA'
                )
                RETURNING
                    id,
                    request_no,
                    requester_id,
                    proposed_name,
                    description,
                    unit,
                    material_group,
                    status,
                    created_at,
                    updated_at
                """
            ),
            {
                "request_no": request_no,
                "requester_id": requester_id,
                "proposed_name": payload.proposed_name.strip(),
                "description": payload.description,
                "unit": payload.unit,
                "material_group": payload.material_group,
            },
        )
        created = dict(insert_result.mappings().one())

        await conn.execute(
            text(
                """
                INSERT INTO request_history (
                    request_id,
                    actor_id,
                    action,
                    from_status,
                    to_status,
                    note
                )
                VALUES (
                    :request_id,
                    :actor_id,
                    'CREATE_REQUEST',
                    NULL,
                    'PENDING_MASTERDATA',
                    'Yêu cầu được tạo từ Material Masterdata Portal V1.3'
                )
                """
            ),
            {
                "request_id": created["id"],
                "actor_id": requester_id,
            },
        )

    return created

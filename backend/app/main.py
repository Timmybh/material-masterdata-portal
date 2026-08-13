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
    version="1.4.0",
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
    requester_email: str = Field(default="user@example.com", max_length=255)


class WorkflowTransition(BaseModel):
    action: str = Field(max_length=50)
    actor_email: str = Field(max_length=255)
    note: str | None = Field(default=None, max_length=4000)
    material_code: str | None = Field(default=None, max_length=100)


def request_select_sql(where_clause: str = "") -> str:
    return f"""
        SELECT
            r.id,
            r.request_no,
            r.requester_id,
            u.email AS requester_email,
            u.full_name AS requester_name,
            r.proposed_name,
            r.description,
            r.unit,
            r.material_group,
            r.status,
            r.masterdata_note,
            r.accounting_note,
            r.result_material_code,
            r.created_at,
            r.updated_at
        FROM material_requests r
        LEFT JOIN users u ON u.id = r.requester_id
        {where_clause}
    """


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
        "version": "1.4.0",
    }


@app.get("/api/v1")
async def api_root():
    return {
        "name": "Material Masterdata Portal",
        "version": "1.4.0",
        "workflow": [
            "PENDING_MASTERDATA",
            "PENDING_ACCOUNTING",
            "PENDING_CODE_ASSIGNMENT",
            "COMPLETED",
            "REJECTED",
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

    return {"query": keyword, "count": len(rows), "items": rows}


@app.post("/api/v1/requests", status_code=201)
async def create_material_request(payload: MaterialRequestCreate):
    request_no = (
        f"REQ-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-"
        f"{uuid4().hex[:6].upper()}"
    )

    async with engine.begin() as conn:
        requester_result = await conn.execute(
            text(
                """
                SELECT id, email, full_name, role
                FROM users
                WHERE email = :email AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"email": payload.requester_email},
        )
        requester = requester_result.mappings().one_or_none()

        if requester is None:
            raise HTTPException(status_code=400, detail="Người tạo yêu cầu không tồn tại hoặc đã bị khóa")

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
                RETURNING id
                """
            ),
            {
                "request_no": request_no,
                "requester_id": requester["id"],
                "proposed_name": payload.proposed_name.strip(),
                "description": payload.description or None,
                "unit": payload.unit or None,
                "material_group": payload.material_group or None,
            },
        )
        request_id = insert_result.scalar_one()

        await conn.execute(
            text(
                """
                INSERT INTO request_history (
                    request_id, actor_id, action, from_status, to_status, note
                )
                VALUES (
                    :request_id, :actor_id, 'CREATE_REQUEST', NULL,
                    'PENDING_MASTERDATA', 'Tạo yêu cầu đặt mã hàng'
                )
                """
            ),
            {"request_id": request_id, "actor_id": requester["id"]},
        )

        result = await conn.execute(
            text(request_select_sql("WHERE r.id = :request_id")),
            {"request_id": request_id},
        )
        created = dict(result.mappings().one())

    return created


@app.get("/api/v1/requests")
async def list_requests(
    status: str | None = Query(default=None, max_length=50),
    requester_email: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=200),
):
    conditions: list[str] = []
    params: dict[str, object] = {"limit": limit}

    if status:
        conditions.append("r.status = :status")
        params["status"] = status
    if requester_email:
        conditions.append("u.email = :requester_email")
        params["requester_email"] = requester_email

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = text(request_select_sql(where) + " ORDER BY r.created_at DESC LIMIT :limit")

    async with engine.connect() as conn:
        result = await conn.execute(sql, params)
        rows = [dict(row) for row in result.mappings().all()]

    return {"count": len(rows), "items": rows}


@app.get("/api/v1/requests/{request_id}")
async def get_request(request_id: int):
    async with engine.connect() as conn:
        request_result = await conn.execute(
            text(request_select_sql("WHERE r.id = :request_id")),
            {"request_id": request_id},
        )
        request_row = request_result.mappings().one_or_none()
        if request_row is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu")

        history_result = await conn.execute(
            text(
                """
                SELECT
                    h.id,
                    h.action,
                    h.from_status,
                    h.to_status,
                    h.note,
                    h.created_at,
                    u.full_name AS actor_name,
                    u.email AS actor_email,
                    u.role AS actor_role
                FROM request_history h
                LEFT JOIN users u ON u.id = h.actor_id
                WHERE h.request_id = :request_id
                ORDER BY h.created_at, h.id
                """
            ),
            {"request_id": request_id},
        )
        history = [dict(row) for row in history_result.mappings().all()]

    return {"request": dict(request_row), "history": history}


@app.post("/api/v1/requests/{request_id}/transition")
async def transition_request(request_id: int, payload: WorkflowTransition):
    action = payload.action.strip().upper()

    async with engine.begin() as conn:
        actor_result = await conn.execute(
            text(
                """
                SELECT id, email, full_name, role
                FROM users
                WHERE email = :email AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"email": payload.actor_email},
        )
        actor = actor_result.mappings().one_or_none()
        if actor is None:
            raise HTTPException(status_code=400, detail="Người xử lý không tồn tại hoặc đã bị khóa")

        current_result = await conn.execute(
            text("SELECT * FROM material_requests WHERE id = :request_id FOR UPDATE"),
            {"request_id": request_id},
        )
        current = current_result.mappings().one_or_none()
        if current is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu")

        from_status = current["status"]
        to_status: str | None = None
        update_fields: list[str] = ["updated_at = NOW()"]
        params: dict[str, object] = {"request_id": request_id}

        if action == "REJECT":
            if from_status not in {"PENDING_MASTERDATA", "PENDING_ACCOUNTING", "PENDING_CODE_ASSIGNMENT"}:
                raise HTTPException(status_code=400, detail="Yêu cầu hiện tại không thể từ chối")
            if actor["role"] not in {"MASTERDATA", "ACCOUNTING"}:
                raise HTTPException(status_code=403, detail="Vai trò hiện tại không có quyền từ chối")
            to_status = "REJECTED"

        elif action == "APPROVE" and from_status == "PENDING_MASTERDATA":
            if actor["role"] != "MASTERDATA":
                raise HTTPException(status_code=403, detail="Chỉ Masterdata được duyệt bước này")
            to_status = "PENDING_ACCOUNTING"
            update_fields.append("masterdata_note = :note")
            params["note"] = payload.note

        elif action == "APPROVE" and from_status == "PENDING_ACCOUNTING":
            if actor["role"] != "ACCOUNTING":
                raise HTTPException(status_code=403, detail="Chỉ Kế toán được duyệt bước này")
            to_status = "PENDING_CODE_ASSIGNMENT"
            update_fields.append("accounting_note = :note")
            params["note"] = payload.note

        elif action == "ASSIGN_CODE" and from_status == "PENDING_CODE_ASSIGNMENT":
            if actor["role"] != "MASTERDATA":
                raise HTTPException(status_code=403, detail="Chỉ Masterdata được cấp mã vật tư")
            if not payload.material_code or not payload.material_code.strip():
                raise HTTPException(status_code=400, detail="Cần nhập mã vật tư kết quả")
            to_status = "COMPLETED"
            update_fields.append("result_material_code = :material_code")
            params["material_code"] = payload.material_code.strip()

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Thao tác {action} không hợp lệ khi yêu cầu ở trạng thái {from_status}",
            )

        params["to_status"] = to_status
        update_fields.append("status = :to_status")

        await conn.execute(
            text(
                f"UPDATE material_requests SET {', '.join(update_fields)} WHERE id = :request_id"
            ),
            params,
        )

        await conn.execute(
            text(
                """
                INSERT INTO request_history (
                    request_id, actor_id, action, from_status, to_status, note
                )
                VALUES (
                    :request_id, :actor_id, :action, :from_status, :to_status, :note
                )
                """
            ),
            {
                "request_id": request_id,
                "actor_id": actor["id"],
                "action": action,
                "from_status": from_status,
                "to_status": to_status,
                "note": payload.note,
            },
        )

        updated_result = await conn.execute(
            text(request_select_sql("WHERE r.id = :request_id")),
            {"request_id": request_id},
        )
        updated = dict(updated_result.mappings().one())

    return updated

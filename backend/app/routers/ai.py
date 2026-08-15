import json

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session
from unidecode import unidecode

from ..auth import current_user
from ..config import get_settings
from ..db import get_db
from ..models import Item, User
from ..schemas import DuplicateCandidateOut, DuplicateCheckIn, DuplicateCheckOut, NameSuggestionIn, NameSuggestionOut

router = APIRouter(prefix="/api/ai", tags=["ai"])
settings = get_settings()


def _extract_output_text(data: dict) -> str:
    for output in data.get("output", []):
        for content in output.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")
    return ""


@router.post("/duplicate-check", response_model=DuplicateCheckOut)
def duplicate_check(payload: DuplicateCheckIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Dò trùng bằng PostgreSQL; không gọi AI và không phát sinh chi phí API."""
    query_text = " ".join(
        value.strip() for value in [payload.item_name, payload.specification, payload.purpose] if value and value.strip()
    )
    normalized = unidecode(query_text).lower()
    compare_text = func.unaccent(func.lower(func.concat_ws(" ", Item.name, Item.name2, Item.item_custom, Item.product_cost_info)))
    score = func.similarity(compare_text, normalized).label("similarity")
    rows = db.execute(
        select(Item, score)
        .where(Item.is_active.is_(True), Item.is_group.is_(False))
        .order_by(desc(score), Item.code)
        .limit(max(payload.limit * 3, 20))
    ).all()
    candidates = [
        DuplicateCandidateOut(
            code=item.code,
            name=item.name,
            similarity=round(float(similarity or 0), 4),
            reason="Tên, tính chất hoặc mục đích sử dụng có nội dung tương đồng.",
            duplicate_risk="HIGH" if float(similarity or 0) >= 0.55 else "POSSIBLE",
        )
        for item, similarity in rows
        if float(similarity or 0) >= 0.08
    ][:payload.limit]
    return DuplicateCheckOut(
        ai_used=False,
        summary=(
            "Đã tìm thấy các mặt hàng tương đồng trong PostgreSQL. Cần kiểm tra trước khi tạo mã mới."
            if candidates else "Chưa tìm thấy mặt hàng tương đồng rõ ràng trong danh mục hiện tại."
        ),
        candidates=candidates,
    )


@router.post("/suggest-name", response_model=NameSuggestionOut)
def suggest_name(payload: NameSuggestionIn, _: User = Depends(current_user)):
    """AI chỉ đề xuất tên mặt hàng chuẩn; không tạo mã và không dò trùng."""
    if not settings.openai_api_key:
        raise HTTPException(503, "Chưa cấu hình OPENAI_API_KEY tại backend")
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"suggested_name": {"type": "string"}, "explanation": {"type": "string"}},
        "required": ["suggested_name", "explanation"],
    }
    input_data = {
        "current_name": payload.item_name,
        "properties": payload.specification or "",
        "technical_specs": payload.technical_specs or "",
        "purpose": payload.purpose or "",
    }
    body = {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": (
                "Bạn đề xuất tên mặt hàng chuẩn, ngắn gọn, dễ tra cứu cho doanh nghiệp sản xuất may mặc. "
                "Chỉ dựa trên tên hiện tại, tính chất/quy cách, thông số kỹ thuật và mục đích sử dụng. "
                "Không tự thêm chủng loại, nhãn hiệu hoặc thông tin không có trong dữ liệu. "
                "Giữ nguyên mã model và thông số kỹ thuật quan trọng. Trả lời bằng tiếng Việt."
            )}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(input_data, ensure_ascii=False)}]},
        ],
        "text": {"format": {"type": "json_schema", "name": "name_suggestion", "strict": True, "schema": schema}},
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        result = json.loads(_extract_output_text(response.json()))
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        raise HTTPException(502, f"OpenAI API từ chối yêu cầu (HTTP {status})") from exc
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise HTTPException(502, "Không thể nhận đề xuất tên mặt hàng từ OpenAI") from exc
    return NameSuggestionOut(**result)

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from unidecode import unidecode

from ..auth import current_user
from ..db import get_db
from ..models import Item, User
from ..schemas import ItemOut, ItemSearchOut

router = APIRouter(prefix="/api/items", tags=["items"])


def _contains_query(value: str) -> str:
    tokens = [token.replace('"', '') for token in value.split() if token]
    return " OR ".join(f'"{token}*"' for token in tokens)


@router.get("/search", response_model=ItemSearchOut)
def search_items(q: str = Query(min_length=1, max_length=200), limit: int = Query(20, ge=1, le=100), item_type: str | None = None, item_group: str | None = None, include_groups: bool = False, db: Session = Depends(get_db), _: User = Depends(current_user)):
    normalized = " ".join(unidecode(q).lower().split())
    filters = ["i.is_active=1", "(:include_groups=1 OR i.is_group=0)"]
    params = {"fts": _contains_query(normalized), "like": f"%{normalized}%", "exact": normalized, "include_groups": int(include_groups), "limit": limit}
    if item_type:
        filters.append("i.item_type_name=:item_type")
        params["item_type"] = item_type
    if item_group:
        filters.append("i.item_group_code=:item_group")
        params["item_group"] = item_group
    where = " AND ".join(filters)
    ranked = db.execute(text(f"""
        SELECT TOP (:limit) i.id, COALESCE(ft.[RANK],0) +
            CASE WHEN LOWER(i.code)=:exact THEN 2000 WHEN LOWER(i.code) LIKE :like THEN 800 ELSE 0 END AS score
        FROM items i
        LEFT JOIN CONTAINSTABLE(items, (search_text, code, name, name2), :fts) ft ON ft.[KEY]=i.id
        WHERE {where} AND (ft.[KEY] IS NOT NULL OR LOWER(i.search_text) LIKE :like OR LOWER(i.code) LIKE :like)
        ORDER BY score DESC, i.code
    """), params).all()
    ids = [row.id for row in ranked]
    by_id = {item.id: item for item in db.scalars(select(Item).where(Item.id.in_(ids))).all()} if ids else {}
    items = []
    for row in ranked:
        item = by_id.get(row.id)
        if item:
            out = ItemOut.model_validate(item)
            out.score = float(row.score or 0)
            items.append(out)
    return ItemSearchOut(items=items, total=len(items), limit=limit, query=q)


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Không tìm thấy vật tư")
    return item


@router.get("", response_model=list[ItemOut])
def list_items(parent_id: int | None = None, is_group: bool | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(Item).order_by(Item.is_group.desc(), Item.code).limit(limit)
    if parent_id is not None:
        query = query.where(Item.parent_id == parent_id)
    if is_group is not None:
        query = query.where(Item.is_group == is_group)
    return db.scalars(query).all()

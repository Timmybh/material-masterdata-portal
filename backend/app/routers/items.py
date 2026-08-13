from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import and_,desc,func,or_,select
from sqlalchemy.orm import Session
from unidecode import unidecode
from ..auth import current_user
from ..db import get_db
from ..models import Item,User
from ..schemas import ItemOut,ItemSearchOut
router=APIRouter(prefix="/api/items",tags=["items"])
@router.get("/search",response_model=ItemSearchOut)
def search_items(q:str=Query(min_length=1,max_length=200),limit:int=Query(20,ge=1,le=100),item_type:str|None=None,item_group:str|None=None,include_groups:bool=False,db:Session=Depends(get_db),_:User=Depends(current_user)):
    nq=" ".join(unidecode(q).lower().split());tokens=nq.split();tsq=func.websearch_to_tsquery("simple",nq);tsv=func.to_tsvector("simple",Item.search_text)
    score=(func.ts_rank_cd(tsv,tsq)*3+func.similarity(Item.search_text,nq)+func.similarity(func.lower(Item.code),nq)*1.5).label("score")
    all_tokens=[Item.search_text.ilike(f"%{token}%") for token in tokens]
    conditions=[Item.is_active.is_(True),or_(tsv.op("@@")(tsq),and_(*all_tokens),Item.search_text.op("%")(nq),func.lower(Item.code).op("%")(nq),func.lower(Item.code).contains(nq),func.lower(func.coalesce(Item.old_code,"")).contains(nq),func.lower(func.coalesce(Item.new_code,"")).contains(nq))]
    if not include_groups:conditions.append(Item.is_group.is_(False))
    if item_type:conditions.append(Item.item_type_name==item_type)
    if item_group:conditions.append(Item.item_group_code==item_group)
    total=db.scalar(select(func.count()).select_from(Item).where(*conditions)) or 0
    rows=db.execute(select(Item,score).where(*conditions).order_by(desc(score),Item.code).limit(limit)).all();items=[]
    for item,s in rows:
        out=ItemOut.model_validate(item);out.score=float(s or 0);items.append(out)
    return ItemSearchOut(items=items,total=total,limit=limit,query=q)
@router.get("/{item_id}",response_model=ItemOut)
def get_item(item_id:int,db:Session=Depends(get_db),_:User=Depends(current_user)):
    item=db.get(Item,item_id)
    if not item:raise HTTPException(404,"Không tìm thấy vật tư")
    return item
@router.get("",response_model=list[ItemOut])
def list_items(parent_id:int|None=None,is_group:bool|None=None,limit:int=Query(100,ge=1,le=500),db:Session=Depends(get_db),_:User=Depends(current_user)):
    q=select(Item).order_by(Item.is_group.desc(),Item.code).limit(limit)
    if parent_id is not None:q=q.where(Item.parent_id==parent_id)
    if is_group is not None:q=q.where(Item.is_group==is_group)
    return db.scalars(q).all()

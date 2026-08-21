from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session,joinedload
from ..auth import require_roles
from ..db import get_db
from ..models import MaterialRequest,RequestStatus,Role,User
from ..notifications import notify
from ..schemas import MasterdataUpdate,ReasonIn,RequestOut
from ..workflow import transition
from .catalogs import resolve_catalog_names
router=APIRouter(prefix="/api/masterdata",tags=["masterdata"]);allowed=require_roles(Role.MASTERDATA.value)
def load(db,rid):
    req=db.scalar(select(MaterialRequest).options(joinedload(MaterialRequest.requester)).where(MaterialRequest.id==rid))
    if not req:raise HTTPException(404,"Không tìm thấy yêu cầu")
    return req
@router.get("/requests",response_model=list[RequestOut])
def queue(db:Session=Depends(get_db),_:User=Depends(allowed)):
    return db.scalars(select(MaterialRequest).options(joinedload(MaterialRequest.requester)).where(MaterialRequest.status.in_([RequestStatus.SUBMITTED.value,RequestStatus.ACCOUNTING_RETURNED.value])).order_by(MaterialRequest.submitted_at)).all()
@router.get("/requests/all",response_model=list[RequestOut])
def all_requests(db:Session=Depends(get_db),_:User=Depends(allowed)):
    return db.scalars(select(MaterialRequest).options(joinedload(MaterialRequest.requester)).order_by(MaterialRequest.code_issued_at.desc().nullslast(),MaterialRequest.updated_at.desc())).all()
@router.patch("/requests/{rid}",response_model=RequestOut)
def update(rid:UUID,payload:MasterdataUpdate,db:Session=Depends(get_db),_:User=Depends(allowed)):
    req=load(db,rid)
    if req.status not in [RequestStatus.SUBMITTED.value,RequestStatus.ACCOUNTING_RETURNED.value]:raise HTTPException(409,"Trạng thái không cho phép sửa")
    data=payload.model_dump(exclude_unset=True)
    if "item_type_name" in data or "item_group" in data:
        data["item_type_name"],data["item_group"]=resolve_catalog_names(db,data.get("item_type_name",req.item_type_name),data.get("item_group",req.item_group))
    for k,v in data.items():setattr(req,k,v)
    db.commit();db.refresh(req);return req
@router.post("/requests/{rid}/approve",response_model=RequestOut)
def approve(rid:UUID,db:Session=Depends(get_db),user:User=Depends(allowed)):
    req=load(db,rid)
    if req.status not in [RequestStatus.SUBMITTED.value,RequestStatus.ACCOUNTING_RETURNED.value]:raise HTTPException(409,"Trạng thái không thể duyệt")
    if not req.item_group or not req.item_type_name:raise HTTPException(422,"Cần chọn Phân loại và Nhóm hàng trước khi duyệt")
    req=transition(db,req,user,"MASTERDATA_APPROVE",RequestStatus.MASTERDATA_APPROVED.value);notify(req.requester.email,f"Masterdata đã duyệt: {req.item_name}",req,"Yêu cầu đã chuyển đến Kế toán.");return req
@router.post("/requests/{rid}/return",response_model=RequestOut)
def return_to_user(rid:UUID,payload:ReasonIn,db:Session=Depends(get_db),user:User=Depends(allowed)):
    req=load(db,rid)
    if req.status not in [RequestStatus.SUBMITTED.value,RequestStatus.ACCOUNTING_RETURNED.value]:raise HTTPException(409,"Trạng thái không thể trả lại")
    req=transition(db,req,user,"MASTERDATA_RETURN",RequestStatus.MASTERDATA_RETURNED.value,payload.reason);req.returned_reason=payload.reason;db.commit();db.refresh(req)
    notify(req.requester.email,f"Yêu cầu cần bổ sung: {req.item_name}",req,f"Lý do trả lại: {payload.reason}\nAnh/chị có thể sửa và gửi duyệt lại trên hệ thống.");return req

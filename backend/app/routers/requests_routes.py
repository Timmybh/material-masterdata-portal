from datetime import datetime,timezone
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session,joinedload
from ..auth import current_user
from ..db import get_db
from ..models import MaterialRequest,RequestAudit,RequestStatus,User
from ..notifications import notify
from ..schemas import RequestCreate,RequestOut,RequestUpdate
from .catalogs import resolve_catalog_names
router=APIRouter(prefix="/api/requests",tags=["requests"])
def load_owned(db,rid,user):
    req=db.scalar(select(MaterialRequest).options(joinedload(MaterialRequest.requester)).where(MaterialRequest.id==rid,MaterialRequest.requester_id==user.id))
    if not req:raise HTTPException(404,"Không tìm thấy yêu cầu")
    return req
@router.post("",response_model=RequestOut)
def create_request(payload:RequestCreate,db:Session=Depends(get_db),user:User=Depends(current_user)):
    data=payload.model_dump();data["item_type_name"],data["item_group"]=resolve_catalog_names(db,data.get("item_type_name"),data.get("item_group"))
    req=MaterialRequest(requester_id=user.id,**data,status=RequestStatus.SUBMITTED.value)
    db.add(req);db.flush();db.add(RequestAudit(request_id=req.id,actor_id=user.id,action="SUBMIT",to_status=req.status));db.commit()
    req=load_owned(db,req.id,user);notify(user.email,f"Đã gửi yêu cầu đặt mã: {req.item_name}",req,"Yêu cầu đã chuyển đến Nhân sự phụ trách Masterdata.");return req
@router.get("/my",response_model=list[RequestOut])
def my_requests(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return db.scalars(select(MaterialRequest).options(joinedload(MaterialRequest.requester)).where(MaterialRequest.requester_id==user.id).order_by(MaterialRequest.updated_at.desc())).all()
@router.patch("/{rid}",response_model=RequestOut)
def edit_returned(rid:UUID,payload:RequestUpdate,db:Session=Depends(get_db),user:User=Depends(current_user)):
    req=load_owned(db,rid,user)
    if req.status!=RequestStatus.MASTERDATA_RETURNED.value:raise HTTPException(409,"Chỉ được sửa yêu cầu đã trả lại")
    data=payload.model_dump();data["item_type_name"],data["item_group"]=resolve_catalog_names(db,data.get("item_type_name"),data.get("item_group"))
    for k,v in data.items():setattr(req,k,v)
    db.add(RequestAudit(request_id=req.id,actor_id=user.id,action="EDIT_RETURNED",from_status=req.status,to_status=req.status));db.commit();db.refresh(req);return req
@router.post("/{rid}/resubmit",response_model=RequestOut)
def resubmit(rid:UUID,db:Session=Depends(get_db),user:User=Depends(current_user)):
    req=load_owned(db,rid,user)
    if req.status!=RequestStatus.MASTERDATA_RETURNED.value:raise HTTPException(409,"Yêu cầu không ở trạng thái chờ gửi lại")
    old=req.status;req.status=RequestStatus.SUBMITTED.value;req.returned_reason=None;req.submitted_at=datetime.now(timezone.utc)
    db.add(RequestAudit(request_id=req.id,actor_id=user.id,action="RESUBMIT",from_status=old,to_status=req.status));db.commit();db.refresh(req)
    notify(user.email,f"Đã gửi duyệt lại: {req.item_name}",req,"Yêu cầu đã được gửi lại đến Nhân sự phụ trách Masterdata.");return req

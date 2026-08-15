from io import BytesIO
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session,joinedload
from ..auth import require_roles
from ..db import get_db
from ..models import MaterialRequest,RequestStatus,Role,User
from ..notifications import notify
from ..schemas import CompleteIn,ReasonIn,RequestOut
from ..workflow import transition
router=APIRouter(prefix="/api/accounting",tags=["accounting"]);allowed=require_roles(Role.ACCOUNTING.value)
def load(db,rid):
    req=db.scalar(select(MaterialRequest).options(joinedload(MaterialRequest.requester)).where(MaterialRequest.id==rid))
    if not req:raise HTTPException(404,"Không tìm thấy yêu cầu")
    return req
@router.get("/requests",response_model=list[RequestOut])
def queue(db:Session=Depends(get_db),_:User=Depends(allowed)):
    return db.scalars(select(MaterialRequest).options(joinedload(MaterialRequest.requester)).where(MaterialRequest.status==RequestStatus.MASTERDATA_APPROVED.value).order_by(MaterialRequest.submitted_at)).all()
@router.get("/export.xlsx")
def export_excel(ids:str=Query(default=""),db:Session=Depends(get_db),_:User=Depends(allowed)):
    q=select(MaterialRequest).options(joinedload(MaterialRequest.requester)).where(MaterialRequest.status==RequestStatus.MASTERDATA_APPROVED.value)
    if ids:q=q.where(MaterialRequest.id.in_([UUID(x.strip()) for x in ids.split(",") if x.strip()]))
    rows=db.scalars(q.order_by(MaterialRequest.submitted_at)).all();wb=Workbook();ws=wb.active;ws.title="BRAVO_IMPORT_PENDING"
    ws.append(["RequestId","ItemName","Unit","ItemTypeName","ParentCode","ItemGroupCode","KindCode","CustomerCode","BranchCode","IsMaterial","WithColor","WithSize","WithArt","Specification","TechnicalSpecs","Purpose","Notes","Requester","SubmittedAt"])
    for r in rows:ws.append([str(r.id),r.item_name,r.unit,r.item_type_name,r.parent_code,r.item_group,r.kind_code,r.customer_code,r.branch_code,r.is_material,r.with_color,r.with_size,r.with_art,r.specification,r.technical_specs,r.purpose,r.notes,r.requester.email,r.submitted_at])
    ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions;bio=BytesIO();wb.save(bio);bio.seek(0)
    return StreamingResponse(bio,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":"attachment; filename=bravo-import-pending.xlsx"})
@router.post("/requests/{rid}/complete",response_model=RequestOut)
def complete(rid:UUID,payload:CompleteIn,db:Session=Depends(get_db),user:User=Depends(allowed)):
    req=load(db,rid)
    if req.status!=RequestStatus.MASTERDATA_APPROVED.value:raise HTTPException(409,"Yêu cầu chưa ở trạng thái Kế toán xử lý")
    req.result_item_code=payload.item_code.strip();req.accounting_note=(payload.note or "").strip() or None
    audit_note=f"Mã mới: {req.result_item_code}"+(f" | Ghi chú: {req.accounting_note}" if req.accounting_note else "")
    req=transition(db,req,user,"ACCOUNTING_COMPLETE",RequestStatus.COMPLETED.value,audit_note)
    notify(req.requester.email,f"Đã có mã vật tư: {req.item_name}",req,f"Mã vật tư mới: {req.result_item_code}");return req
@router.post("/requests/{rid}/return",response_model=RequestOut)
def return_to_masterdata(rid:UUID,payload:ReasonIn,db:Session=Depends(get_db),user:User=Depends(allowed)):
    req=load(db,rid)
    if req.status!=RequestStatus.MASTERDATA_APPROVED.value:raise HTTPException(409,"Trạng thái không thể trả lại")
    req=transition(db,req,user,"ACCOUNTING_RETURN",RequestStatus.ACCOUNTING_RETURNED.value,payload.reason);notify(req.requester.email,f"Kế toán trả yêu cầu: {req.item_name}",req,f"Lý do: {payload.reason}");return req

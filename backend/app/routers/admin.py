import asyncio
import shutil
from pathlib import Path
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,File,HTTPException,Query,UploadFile,status
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import require_roles
from ..db import get_db
from ..auto_import import ImportAlreadyRunningError,enqueue_import_job,get_import_config,get_import_job,get_import_spool_dir,import_is_running
from ..models import AutoImportConfig,ImportRunHistory,MaterialRequest,RequestAudit,Role,User,UserAudit
from ..passwords import hash_password
from ..schemas import AdminPasswordReset,AdminUserCreate,AutoImportConfigOut,AutoImportConfigUpdate,ImportJobOut,ImportRunHistoryOut,UserOut,UserRoleUpdate
router=APIRouter(prefix="/api/admin",tags=["admin"]);allowed=require_roles(Role.ADMIN.value)

def _persist_uploaded_file(source, target_path:Path):
    with target_path.open("xb") as target:
        shutil.copyfileobj(source,target)

def import_config_out(config:AutoImportConfig,db:Session):
    last_auto=db.scalar(
        select(ImportRunHistory)
        .where(ImportRunHistory.trigger=="AUTO")
        .order_by(ImportRunHistory.queued_at.desc(),ImportRunHistory.id.desc())
        .limit(1)
    )
    return {
        "enabled":config.enabled,"file_path":config.file_path,"hour":config.hour,"minute":config.minute,
        "timezone":config.timezone,"is_running":import_is_running(),"scheduler_active":config.enabled,
        "last_trigger":last_auto.trigger if last_auto else None,
        "last_started_at":last_auto.started_at if last_auto else None,
        "last_completed_at":last_auto.completed_at if last_auto else None,
        "last_status":last_auto.status.upper() if last_auto else None,
        "last_imported":last_auto.imported if last_auto else 0,
        "last_skipped":last_auto.skipped if last_auto else 0,
        "last_error":last_auto.error if last_auto else None,"updated_at":config.updated_at,
    }

@router.get("/item-import/config",response_model=AutoImportConfigOut)
def read_item_import_config(db:Session=Depends(get_db),_:User=Depends(allowed)):
    return import_config_out(get_import_config(db),db)

@router.put("/item-import/config",response_model=AutoImportConfigOut)
def update_item_import_config(payload:AutoImportConfigUpdate,db:Session=Depends(get_db),_:User=Depends(allowed)):
    file_path=payload.file_path.strip()
    if Path(file_path).suffix.lower() not in {".xlsx",".csv"}:
        raise HTTPException(422,"Đường dẫn phải trỏ đến file .xlsx hoặc .csv")
    config=get_import_config(db)
    config.enabled=payload.enabled;config.file_path=file_path;config.hour=payload.hour;config.minute=payload.minute
    db.commit();db.refresh(config)
    return import_config_out(config,db)

@router.get("/item-import/history",response_model=list[ImportRunHistoryOut],status_code=status.HTTP_200_OK)
def read_item_import_history(
    trigger:str|None=Query(default=None,pattern="^(MANUAL|AUTO)$"),
    db:Session=Depends(get_db),_:User=Depends(allowed),
):
    statement=select(ImportRunHistory)
    if trigger:statement=statement.where(ImportRunHistory.trigger==trigger)
    return db.scalars(statement.order_by(ImportRunHistory.queued_at.desc(),ImportRunHistory.id.desc()).limit(20)).all()

@router.get("/item-import/jobs/{job_id}",response_model=ImportJobOut,status_code=status.HTTP_200_OK)
def read_item_import_job(job_id:UUID,db:Session=Depends(get_db),_:User=Depends(allowed)):
    job=get_import_job(db,job_id)
    if not job:raise HTTPException(404,"Không tìm thấy job import")
    return job

@router.post("/item-import/upload",response_model=ImportJobOut,status_code=status.HTTP_202_ACCEPTED)
async def import_items_from_upload(file:UploadFile=File(...),_:User=Depends(allowed)):
    suffix=Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx",".csv"}:
        raise HTTPException(422,"Chỉ hỗ trợ file .xlsx hoặc .csv")
    if import_is_running():
        raise HTTPException(409,"Một tác vụ import khác đang chạy")
    job_id=uuid4()
    spool_path=get_import_spool_dir()/f"{job_id}{suffix}"
    enqueued=False
    try:
        await asyncio.to_thread(_persist_uploaded_file,file.file,spool_path)
        job=enqueue_import_job(
            str(spool_path),"MANUAL",file.filename or spool_path.name,job_id=job_id
        )
        enqueued=True
        return job
    except ImportAlreadyRunningError as exc:
        raise HTTPException(409,str(exc)) from exc
    except (ValueError,FileNotFoundError) as exc:
        raise HTTPException(422,str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422,f"Import thất bại: {exc}") from exc
    finally:
        await file.close()
        # Sau khi enqueue thành công, worker sở hữu file. Nếu không có job tương
        # ứng (copy/enqueue lỗi), xóa file mồ côi ngay.
        if not enqueued:spool_path.unlink(missing_ok=True)
@router.get("/users",response_model=list[UserOut])
def users(db:Session=Depends(get_db),_:User=Depends(allowed)):return db.scalars(select(User).order_by(User.created_at.desc())).all()
@router.post("/users",response_model=UserOut,status_code=201)
def create_user(payload:AdminUserCreate,db:Session=Depends(get_db),_:User=Depends(allowed)):
    email=payload.email.lower().strip();username=payload.username.lower().strip();role=payload.role.upper()
    if role not in {x.value for x in Role}:raise HTTPException(422,"Role không hợp lệ")
    if db.scalar(select(User).where(User.email==email)):raise HTTPException(409,"Email đã tồn tại")
    if db.scalar(select(User).where(User.username==username)):raise HTTPException(409,"Tên tài khoản đã tồn tại")
    user=User(email=email,username=username,password_hash=hash_password(payload.password) if payload.password else None,name=payload.name.strip(),role=role,is_active=payload.is_active)
    db.add(user);db.commit();db.refresh(user);return user
@router.patch("/users/{uid}",response_model=UserOut)
def update_user(uid:UUID,payload:UserRoleUpdate,db:Session=Depends(get_db),actor:User=Depends(allowed)):
    user=db.get(User,uid)
    if not user:raise HTTPException(404,"Không tìm thấy người dùng")
    role=payload.role.upper()
    if role not in {x.value for x in Role}:raise HTTPException(422,"Role không hợp lệ")
    if user.id==actor.id and payload.is_active is False:raise HTTPException(409,"Không thể tự khóa tài khoản")
    if payload.email:
        email=payload.email.lower().strip()
        if db.scalar(select(User).where(User.email==email,User.id!=uid)):raise HTTPException(409,"Email đã được sử dụng")
        user.email=email
    if payload.username:
        username=payload.username.lower().strip()
        if db.scalar(select(User).where(User.username==username,User.id!=uid)):raise HTTPException(409,"Tên tài khoản đã được sử dụng")
        user.username=username
    if payload.name:user.name=payload.name.strip()
    user.role=role
    if payload.is_active is not None:user.is_active=payload.is_active
    db.commit();db.refresh(user);return user

@router.post("/users/{uid}/reset-password",status_code=204)
def reset_password(uid:UUID,payload:AdminPasswordReset,db:Session=Depends(get_db),actor:User=Depends(allowed)):
    user=db.get(User,uid)
    if not user:raise HTTPException(404,"Không tìm thấy người dùng")
    if payload.password!=payload.password_confirmation:raise HTTPException(422,"Mật khẩu xác nhận không khớp")
    user.password_hash=hash_password(payload.password) if payload.password else None
    user.token_version+=1
    db.add(UserAudit(user_id=user.id,actor_id=actor.id,action="PASSWORD_RESET"))
    db.commit()


@router.delete("/users/{uid}")
def delete_user(uid:UUID,db:Session=Depends(get_db),actor:User=Depends(allowed)):
    user=db.get(User,uid)
    if not user:raise HTTPException(404,"Không tìm thấy người dùng")
    if user.id==actor.id:raise HTTPException(409,"Không thể tự xóa tài khoản đang đăng nhập")
    has_history=bool(
        db.scalar(select(MaterialRequest.id).where(MaterialRequest.requester_id==uid).limit(1))
        or db.scalar(select(RequestAudit.id).where(RequestAudit.actor_id==uid).limit(1))
        or db.scalar(select(UserAudit.id).where((UserAudit.user_id==uid)|(UserAudit.actor_id==uid)).limit(1))
    )
    if has_history:
        user.is_active=False;user.token_version+=1
        db.add(UserAudit(user_id=user.id,actor_id=actor.id,action="DELETE_DEACTIVATED"))
        db.commit()
        return {"deleted":False,"deactivated":True,"message":"Tài khoản có lịch sử nghiệp vụ nên đã được khóa để bảo toàn dữ liệu."}
    db.delete(user);db.commit()
    return {"deleted":True,"deactivated":False,"message":"Đã xóa người dùng."}

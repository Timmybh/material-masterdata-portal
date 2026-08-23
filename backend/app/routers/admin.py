import asyncio
import shutil
import tempfile
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter,Depends,File,HTTPException,UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import require_roles
from ..db import get_db
from ..auto_import import ImportAlreadyRunningError,execute_import,get_import_config
from ..models import AutoImportConfig,MaterialRequest,RequestAudit,Role,User,UserAudit
from ..passwords import hash_password
from ..schemas import AdminPasswordReset,AdminUserCreate,AutoImportConfigOut,AutoImportConfigUpdate,UserOut,UserRoleUpdate
router=APIRouter(prefix="/api/admin",tags=["admin"]);allowed=require_roles(Role.ADMIN.value)

def import_config_out(config:AutoImportConfig):
    return {
        "enabled":config.enabled,"file_path":config.file_path,"hour":config.hour,"minute":config.minute,
        "timezone":config.timezone,"is_running":config.is_running,"scheduler_active":config.enabled,
        "last_trigger":config.last_trigger,"last_started_at":config.last_started_at,"last_completed_at":config.last_completed_at,
        "last_status":config.last_status,"last_imported":config.last_imported,"last_skipped":config.last_skipped,
        "last_error":config.last_error,"updated_at":config.updated_at,
    }

@router.get("/item-import/config",response_model=AutoImportConfigOut)
def read_item_import_config(db:Session=Depends(get_db),_:User=Depends(allowed)):
    return import_config_out(get_import_config(db))

@router.put("/item-import/config",response_model=AutoImportConfigOut)
def update_item_import_config(payload:AutoImportConfigUpdate,db:Session=Depends(get_db),_:User=Depends(allowed)):
    file_path=payload.file_path.strip()
    if Path(file_path).suffix.lower() not in {".xlsx",".csv"}:
        raise HTTPException(422,"Đường dẫn phải trỏ đến file .xlsx hoặc .csv")
    config=get_import_config(db)
    config.enabled=payload.enabled;config.file_path=file_path;config.hour=payload.hour;config.minute=payload.minute
    db.commit();db.refresh(config)
    return import_config_out(config)

@router.post("/item-import/upload")
async def import_items_from_upload(file:UploadFile=File(...),_:User=Depends(allowed)):
    suffix=Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx",".csv"}:
        raise HTTPException(422,"Chỉ hỗ trợ file .xlsx hoặc .csv")
    temp_path=None
    try:
        with tempfile.NamedTemporaryFile(prefix="admin-item-import-",suffix=suffix,delete=False) as target:
            temp_path=Path(target.name)
            shutil.copyfileobj(file.file,target)
        result=await asyncio.to_thread(execute_import,str(temp_path),"MANUAL")
        return {"message":"Import danh mục vật tư thành công",**result}
    except ImportAlreadyRunningError as exc:
        raise HTTPException(409,str(exc)) from exc
    except (ValueError,FileNotFoundError) as exc:
        raise HTTPException(422,str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422,f"Import thất bại: {exc}") from exc
    finally:
        await file.close()
        if temp_path:
            temp_path.unlink(missing_ok=True)
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

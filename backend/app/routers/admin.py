from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import require_roles
from ..db import get_db
from ..models import Role,User
from ..schemas import UserOut,UserRoleUpdate
router=APIRouter(prefix="/api/admin",tags=["admin"]);allowed=require_roles(Role.ADMIN.value)
@router.get("/users",response_model=list[UserOut])
def users(db:Session=Depends(get_db),_:User=Depends(allowed)):return db.scalars(select(User).order_by(User.created_at.desc())).all()
@router.patch("/users/{uid}",response_model=UserOut)
def update_user(uid:UUID,payload:UserRoleUpdate,db:Session=Depends(get_db),actor:User=Depends(allowed)):
    user=db.get(User,uid)
    if not user:raise HTTPException(404,"Không tìm thấy người dùng")
    role=payload.role.upper()
    if role not in {x.value for x in Role}:raise HTTPException(422,"Role không hợp lệ")
    if user.id==actor.id and payload.is_active is False:raise HTTPException(409,"Không thể tự khóa tài khoản")
    user.role=role
    if payload.is_active is not None:user.is_active=payload.is_active
    db.commit();db.refresh(user);return user

from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import require_roles
from ..db import get_db
from ..models import Role,User
from ..passwords import hash_password
from ..schemas import AdminUserCreate,UserOut,UserRoleUpdate
router=APIRouter(prefix="/api/admin",tags=["admin"]);allowed=require_roles(Role.ADMIN.value)
@router.get("/users",response_model=list[UserOut])
def users(db:Session=Depends(get_db),_:User=Depends(allowed)):return db.scalars(select(User).order_by(User.created_at.desc())).all()
@router.post("/users",response_model=UserOut,status_code=201)
def create_user(payload:AdminUserCreate,db:Session=Depends(get_db),_:User=Depends(allowed)):
    email=payload.email.lower().strip();username=payload.username.lower().strip();role=payload.role.upper()
    if role not in {x.value for x in Role}:raise HTTPException(422,"Role không hợp lệ")
    if db.scalar(select(User).where(User.email==email)):raise HTTPException(409,"Email đã tồn tại")
    if db.scalar(select(User).where(User.username==username)):raise HTTPException(409,"Tên tài khoản đã tồn tại")
    user=User(email=email,username=username,password_hash=hash_password(payload.password),name=payload.name.strip(),role=role,is_active=payload.is_active)
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
    if payload.password:user.password_hash=hash_password(payload.password)
    db.commit();db.refresh(user);return user

from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import get_settings
from .db import get_db
from .models import User, Role

settings = get_settings()
security = HTTPBearer(auto_error=False)


def role_for_email(email: str) -> str:
    e = email.lower()
    if e in settings.email_set(settings.bootstrap_admin_emails):
        return Role.ADMIN.value
    if e in settings.email_set(settings.accounting_emails):
        return Role.ACCOUNTING.value
    if e in settings.email_set(settings.masterdata_emails):
        return Role.MASTERDATA.value
    return Role.USER.value


def upsert_google_user(db: Session, credential: str) -> User:
    if not settings.google_client_id:
        raise HTTPException(503, "GOOGLE_CLIENT_ID chưa được cấu hình")
    try:
        payload = id_token.verify_oauth2_token(credential, google_requests.Request(), settings.google_client_id)
    except Exception as exc:
        raise HTTPException(401, f"Google token không hợp lệ: {exc}")
    if not payload.get("email_verified"):
        raise HTTPException(401, "Email Google chưa được xác minh")
    email = payload["email"].lower()
    user = db.scalar(select(User).where(User.email == email))
    desired_role = role_for_email(email)
    if not user:
        user = User(email=email, name=payload.get("name", email), picture=payload.get("picture"), role=desired_role)
        db.add(user)
    else:
        user.name = payload.get("name", user.name)
        user.picture = payload.get("picture", user.picture)
        if desired_role != Role.USER.value:
            user.role = desired_role
    db.commit(); db.refresh(user)
    return user


def create_token(user: User) -> str:
    if not user.is_active:
        raise HTTPException(403, "Tài khoản đã bị khóa")
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_exp_minutes)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chưa đăng nhập")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        uid = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "Người dùng không tồn tại")
    if not user.is_active:
        raise HTTPException(403, "Tài khoản đã bị khóa")
    return user


def require_roles(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles and user.role != Role.ADMIN.value:
            raise HTTPException(403, "Bạn không có quyền thực hiện chức năng này")
        return user
    return dep

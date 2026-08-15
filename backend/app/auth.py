from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Role, User

settings = get_settings()
security = HTTPBearer(auto_error=False)


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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import create_token, current_user
from ..db import get_db
from ..models import User
from ..passwords import verify_password
from ..schemas import AuthOut, PasswordLoginIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=AuthOut)
def password_login(payload: PasswordLoginIn, db: Session = Depends(get_db)):
    identifier = payload.identifier.strip().lower()
    user = db.scalar(select(User).where(or_(func.lower(User.email) == identifier, func.lower(User.username) == identifier)))
    password_matches = bool(user) and (
        (user.password_hash is None and payload.password == "")
        or verify_password(payload.password, user.password_hash)
    )
    if not user or not user.is_active or not password_matches:
        raise HTTPException(401, "Tài khoản hoặc mật khẩu không đúng")
    return AuthOut(access_token=create_token(user), user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

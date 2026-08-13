from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import upsert_google_user, create_token, current_user, role_for_email
from ..config import get_settings
from ..db import get_db
from ..models import User
from ..schemas import GoogleAuthIn, AuthOut, UserOut, DevAuthIn

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()

@router.post("/google", response_model=AuthOut)
def google_login(payload: GoogleAuthIn, db: Session = Depends(get_db)):
    user = upsert_google_user(db, payload.credential)
    return AuthOut(access_token=create_token(user), user=user)

@router.post("/dev", response_model=AuthOut)
def dev_login(payload: DevAuthIn, db: Session = Depends(get_db)):
    if not settings.dev_auth_enabled:
        raise HTTPException(404, "Dev auth disabled")
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user:
        user = User(email=payload.email.lower(), name=payload.name, role=payload.role.upper(), is_active=True)
        db.add(user)
    else:
        user.role = payload.role.upper(); user.name = payload.name
    db.commit(); db.refresh(user)
    return AuthOut(access_token=create_token(user), user=user)

@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

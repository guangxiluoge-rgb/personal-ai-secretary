from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_current_user_id, hash_password, verify_password
from app.db import get_db
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "email already registered")
    user = User(email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me")
def me(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(401, "user is no longer active")
    return {"id": user.id, "email": user.email, "created_at": user.created_at}

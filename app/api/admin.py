from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.admin_security import create_admin_token, require_admin_secret
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db import get_db
from app.models import User
from app.models.admin import AdminUser
from app.services.admin_service import EDITABLE_KEYS, list_settings, set_setting

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminLoginIn(BaseModel):
    email: str
    password: str

class SettingIn(BaseModel):
    value: str = Field(max_length=10000)

class AdminCreateIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    is_superadmin: bool = False

class AdminPasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=200)

class StatusIn(BaseModel):
    is_active: bool


def _current_admin(db: Session, payload: dict) -> AdminUser:
    try:
        admin_id = int(payload.get("sub", "0"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(403, "Invalid admin identity") from exc
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id, AdminUser.is_active.is_(True)).first()
    if not admin:
        raise HTTPException(403, "Admin account is inactive")
    return admin


def _require_superadmin(db: Session, payload: dict) -> AdminUser:
    admin = _current_admin(db, payload)
    if not admin.is_superadmin:
        raise HTTPException(403, "Superadmin access required")
    return admin

@router.post("/bootstrap")
def bootstrap(db: Session = Depends(get_db)):
    if not settings.admin_bootstrap_email or not settings.admin_bootstrap_password:
        raise HTTPException(503, "Admin bootstrap is not configured")
    if db.query(AdminUser).count() > 0:
        raise HTTPException(409, "Admin already initialized")
    admin = AdminUser(email=settings.admin_bootstrap_email, password_hash=hash_password(settings.admin_bootstrap_password), is_superadmin=True)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return {"status": "initialized", "admin_id": admin.id}

@router.post("/login")
def login(data: AdminLoginIn, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.email == data.email, AdminUser.is_active.is_(True)).first()
    if not admin or not verify_password(data.password, admin.password_hash):
        raise HTTPException(401, "invalid admin credentials")
    return {"access_token": create_admin_token(admin.id), "token_type": "bearer"}

@router.get("/settings")
def settings_list(_: dict = Depends(require_admin_secret), db: Session = Depends(get_db)):
    return {"settings": list_settings(db)}

@router.put("/settings/{key}")
def settings_update(key: str, data: SettingIn, _: dict = Depends(require_admin_secret), db: Session = Depends(get_db)):
    if key not in EDITABLE_KEYS:
        raise HTTPException(404, "setting is not editable")
    row = set_setting(db, key, data.value)
    return {"key": row.key, "updated": True, "is_secret": row.is_secret}

@router.get("/users")
def users_list(q: str = Query(default="", max_length=320), is_active: bool | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), _: dict = Depends(require_admin_secret), db: Session = Depends(get_db)):
    query = db.query(User)
    if q.strip():
        query = query.filter(User.email.ilike(f"%{q.strip()}%"))
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))
    total = query.count()
    rows = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [{"id": u.id, "email": u.email, "is_active": u.is_active, "created_at": u.created_at} for u in rows]}

@router.get("/users/{user_id}")
def user_detail(user_id: int, _: dict = Depends(require_admin_secret), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "user not found")
    return {"id": user.id, "email": user.email, "is_active": user.is_active, "created_at": user.created_at}

@router.patch("/users/{user_id}/status")
def user_status(user_id: int, data: StatusIn, _: dict = Depends(require_admin_secret), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "user not found")
    user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email, "is_active": user.is_active}

@router.get("/admins")
def admin_list(payload: dict = Depends(require_admin_secret), db: Session = Depends(get_db)):
    _require_superadmin(db, payload)
    rows = db.query(AdminUser).order_by(AdminUser.created_at.desc()).limit(200).all()
    return {"items": [{"id": a.id, "email": a.email, "is_active": a.is_active, "is_superadmin": a.is_superadmin, "created_at": a.created_at} for a in rows]}

@router.post("/admins")
def admin_create(data: AdminCreateIn, payload: dict = Depends(require_admin_secret), db: Session = Depends(get_db)):
    _require_superadmin(db, payload)
    if db.query(AdminUser).filter(AdminUser.email == data.email).first():
        raise HTTPException(409, "admin email already exists")
    admin = AdminUser(email=data.email, password_hash=hash_password(data.password), is_superadmin=data.is_superadmin, is_active=True)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return {"id": admin.id, "email": admin.email, "is_active": admin.is_active, "is_superadmin": admin.is_superadmin}

@router.patch("/admins/{admin_id}/status")
def admin_status(admin_id: int, data: StatusIn, payload: dict = Depends(require_admin_secret), db: Session = Depends(get_db)):
    current = _require_superadmin(db, payload)
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not admin:
        raise HTTPException(404, "admin not found")
    if admin.id == current.id and not data.is_active:
        raise HTTPException(400, "cannot disable current admin")
    if admin.is_superadmin and admin.is_active and not data.is_active:
        count = db.query(AdminUser).filter(AdminUser.is_superadmin.is_(True), AdminUser.is_active.is_(True)).count()
        if count <= 1:
            raise HTTPException(400, "cannot disable the last active superadmin")
    admin.is_active = data.is_active
    db.commit()
    db.refresh(admin)
    return {"id": admin.id, "email": admin.email, "is_active": admin.is_active, "is_superadmin": admin.is_superadmin}

@router.post("/admins/{admin_id}/password")
def admin_password(admin_id: int, data: AdminPasswordIn, payload: dict = Depends(require_admin_secret), db: Session = Depends(get_db)):
    _require_superadmin(db, payload)
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not admin:
        raise HTTPException(404, "admin not found")
    admin.password_hash = hash_password(data.password)
    db.commit()
    return {"id": admin.id, "updated": True, "updated_at": datetime.utcnow()}

@router.get("/health")
def admin_health(_: dict = Depends(require_admin_secret)):
    return {"status": "ok", "environment": settings.env}

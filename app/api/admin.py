from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_password
from app.core.admin_security import create_admin_token, require_admin_secret
from app.db import get_db
from app.models.admin import AdminUser
from app.services.admin_service import EDITABLE_KEYS, get_setting, list_settings, set_setting

router = APIRouter(prefix="/api/admin", tags=["admin"])

class AdminLoginIn(BaseModel):
    email: str
    password: str

class SettingIn(BaseModel):
    value: str = Field(max_length=10000)

@router.post("/bootstrap")
def bootstrap(db: Session = Depends(get_db)):
    if not settings.admin_bootstrap_email or not settings.admin_bootstrap_password:
        raise HTTPException(503, "Admin bootstrap is not configured")
    if db.query(AdminUser).count() > 0:
        raise HTTPException(409, "Admin already initialized")
    admin = AdminUser(email=settings.admin_bootstrap_email, password_hash=hash_password(settings.admin_bootstrap_password), is_superadmin=True)
    db.add(admin); db.commit(); db.refresh(admin)
    return {"status": "initialized", "admin_id": admin.id}

@router.post("/login")
def login(data: AdminLoginIn, db: Session = Depends(get_db)):
    from app.core.security import verify_password
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

@router.get("/health")
def admin_health(_: dict = Depends(require_admin_secret)):
    return {"status": "ok", "environment": settings.env}

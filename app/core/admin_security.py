from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.core.config import settings

admin_bearer = HTTPBearer(auto_error=False)

# MVP: admin identities are persisted in AdminUser and receive the same JWT format,
# with an explicit admin claim in a future migration. This module currently exposes
# a dedicated header gate so the admin UI can be wired without weakening user auth.
def require_admin_secret(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(admin_bearer)]):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")
    if payload.get("admin") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return payload

def create_admin_token(admin_id: int) -> str:
    from datetime import datetime, timedelta, timezone
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(admin_id), "admin": True, "exp": exp}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

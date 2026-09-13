from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.core.config import settings
from app.api.auth import router as auth_router
from app.api.memory import router as memory_router
from app.api.ai import router as ai_router
from app.api.admin import router as admin_router

if settings.env.lower() == "production" and settings.jwt_secret == "CHANGE_ME":
    raise RuntimeError("JWT_SECRET must be changed before production startup")

app = FastAPI(title=settings.app_name, version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(memory_router)
app.include_router(ai_router)
app.include_router(admin_router)

@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(Path(__file__).parent / "admin" / "index.html")

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name, "version": app.version}

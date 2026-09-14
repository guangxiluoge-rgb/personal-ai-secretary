from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.admin import router as admin_router
from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.health import router as health_router
from app.api.health_history import router as health_history_router
from app.api.memory import router as memory_router
from app.core.config import settings

if settings.env.lower() == "production" and settings.jwt_secret == "CHANGE_ME":
    raise RuntimeError("JWT_SECRET must be changed before production startup")

app = FastAPI(title=settings.app_name, version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(memory_router)
app.include_router(ai_router)
app.include_router(admin_router)
app.include_router(health_router)
app.include_router(health_history_router)
app.include_router(billing_router)


@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(Path(__file__).parent / "admin" / "index.html")


@app.get("/health/gallery", include_in_schema=False)
def health_gallery_page():
    return FileResponse(Path(__file__).parent / "health" / "index.html")


@app.get("/health/history", include_in_schema=False)
def health_history_page():
    return FileResponse(Path(__file__).parent / "health" / "history.html")


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name, "version": app.version}

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from app.api.admin import router as admin_router
from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.health import router as health_router
from app.api.health_history import router as health_history_router
from app.api.health_long_term import router as health_long_term_router
from app.api.life_os import router as life_os_router
from app.api.memory import router as memory_router
from app.api.social import router as social_router
from app.core.config import settings

if settings.env.lower() == "production" and settings.jwt_secret == "CHANGE_ME":
    raise RuntimeError("JWT_SECRET must be changed before production startup")

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(memory_router)
app.include_router(ai_router)
app.include_router(admin_router)
app.include_router(health_router)
app.include_router(health_history_router)
app.include_router(health_long_term_router)
app.include_router(life_os_router)
app.include_router(social_router)
app.include_router(billing_router)


def _page(path: str) -> HTMLResponse:
    source = (Path(__file__).parent / path).read_text(encoding="utf-8")
    marker = "<html"
    idx = source.lower().find(marker)
    if idx >= 0:
        end = source.find(">", idx) + 1
        source = source[:end] + f'\n<script>document.documentElement.dataset.appVersion={settings.app_version!r}</script><script src="/update.js"></script>' + source[end:]
    return HTMLResponse(source, headers={"Cache-Control": "no-store"})


@app.get("/update.js", include_in_schema=False)
def update_script():
    return FileResponse(Path(__file__).parent / "update.js", media_type="application/javascript", headers={"Cache-Control": "no-store"})


@app.get("/api/system/version", include_in_schema=False)
def system_version():
    return {"version": settings.app_version, "service": settings.app_name}


@app.get("/admin", include_in_schema=False)
def admin_page():
    return _page("admin/index.html")


@app.get("/admin/users", include_in_schema=False)
def admin_users_page():
    return _page("admin/users.html")


@app.get("/health/gallery", include_in_schema=False)
def health_gallery_page():
    return _page("health/index.html")


@app.get("/health/history", include_in_schema=False)
def health_history_page():
    return _page("health/history.html")


@app.get("/health/long-term", include_in_schema=False)
def health_long_term_page():
    return _page("health/long_term.html")


@app.get("/life-os", include_in_schema=False)
def life_os_page():
    return _page("life_os/index.html")


@app.get("/social", include_in_schema=False)
def social_page():
    return _page("social/index.html")


@app.get("/mobile", include_in_schema=False)
def mobile_page():
    return _page("mobile/intelligence.html")


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name, "version": app.version}

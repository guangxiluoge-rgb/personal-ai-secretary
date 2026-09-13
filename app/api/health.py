import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import get_current_user_id
from app.db import get_db
from app.models import HealthAnalysisJob, HealthAlert, HealthRecord

router = APIRouter(prefix="/api/health", tags=["health"])
ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

@router.post("/upload")
async def upload_health_image(file: UploadFile = File(...), image_type: str = "wearable", db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    if file.content_type not in ALLOWED: raise HTTPException(400, "only JPG/PNG/WEBP images are supported")
    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024: raise HTTPException(413, "file too large")
    root = Path(settings.storage_dir) / str(user_id); root.mkdir(parents=True, exist_ok=True)
    path = root / f"{uuid.uuid4().hex}{ALLOWED[file.content_type]}"; path.write_bytes(raw)
    job = HealthAnalysisJob(user_id=user_id, file_path=str(path), image_type=image_type, status="pending")
    db.add(job); db.commit(); db.refresh(job)
    return {"job_id": job.id, "status": job.status, "message": "已进入后台健康分析队列；未完成专业复核前不作为诊断结论。"}

@router.get("/jobs/{job_id}")
def job_status(job_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    job = db.query(HealthAnalysisJob).filter(HealthAnalysisJob.id == job_id, HealthAnalysisJob.user_id == user_id).first()
    if not job: raise HTTPException(404, "job not found")
    return {"id": job.id, "status": job.status, "error": job.error, "created_at": job.created_at, "completed_at": job.completed_at}

@router.get("/records")
def records(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = db.query(HealthRecord).filter(HealthRecord.user_id == user_id).order_by(HealthRecord.created_at.desc()).limit(100).all()
    return [{"id": r.id, "source": r.source, "image_type": r.image_type, "summary": r.summary, "risk_level": r.risk_level, "created_at": r.created_at} for r in rows]

@router.get("/alerts")
def alerts(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = db.query(HealthAlert).filter(HealthAlert.user_id == user_id, HealthAlert.acknowledged.is_(False)).order_by(HealthAlert.created_at.desc()).all()
    return [{"id": a.id, "severity": a.severity, "message": a.message, "created_at": a.created_at} for a in rows]

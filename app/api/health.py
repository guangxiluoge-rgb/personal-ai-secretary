import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user_id
from app.db import get_db
from app.models import HealthAlert, HealthAnalysisJob, HealthRecord
from app.services.health_ingest import classify_candidate

router = APIRouter(prefix="/api/health", tags=["health"])
ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
IMAGE_TYPES = {"wearable", "medical_report", "tongue", "face", "unknown"}
SOURCES = {"gallery", "camera", "file"}


class GalleryCandidate(BaseModel):
    filename: str = Field(default="", max_length=512)
    ocr_text: str = Field(default="", max_length=12000)


class GalleryPreflightIn(BaseModel):
    candidates: list[GalleryCandidate] = Field(default_factory=list, max_length=200)


@router.post("/gallery/preflight")
def gallery_preflight(
    data: GalleryPreflightIn,
    user_id: int = Depends(get_current_user_id),
):
    """Classify gallery candidates locally from metadata/OCR; never calls the LLM."""
    results = []
    for candidate in data.candidates:
        result = classify_candidate(candidate.filename, candidate.ocr_text)
        results.append(
            {
                "filename": candidate.filename,
                "image_type": result.image_type,
                "confidence": result.confidence,
                "reasons": list(result.reasons),
                "should_send_to_ai": result.should_send_to_ai,
            }
        )
    return {
        "user_id": user_id,
        "token_cost": 0,
        "results": results,
        "policy": "local_filter_first",
        "unknown_requires_user_confirmation": True,
    }


@router.post("/upload")
async def upload_health_image(
    file: UploadFile = File(...),
    image_type: str = Form("unknown"),
    source: str = Form("gallery"),
    client_sha256: str | None = Form(None),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    if file.content_type not in ALLOWED:
        raise HTTPException(400, "only JPG/PNG/WEBP images are supported")
    if image_type not in IMAGE_TYPES:
        image_type = "unknown"
    if source not in SOURCES:
        source = "file"

    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "file too large")

    digest = hashlib.sha256(raw).hexdigest()
    if client_sha256 and client_sha256.lower() != digest:
        raise HTTPException(400, "image hash mismatch; please reselect the image")

    duplicate = (
        db.query(HealthAnalysisJob)
        .filter(
            HealthAnalysisJob.user_id == user_id,
            HealthAnalysisJob.client_sha256 == digest,
            HealthAnalysisJob.status.in_(["pending", "running", "completed"]),
        )
        .order_by(HealthAnalysisJob.id.desc())
        .first()
    )
    if duplicate:
        return {
            "job_id": duplicate.id,
            "status": duplicate.status,
            "duplicate": True,
            "message": "这张图片已经提交过，无需重复上传。",
        }

    root = Path(settings.storage_dir) / str(user_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{uuid.uuid4().hex}{ALLOWED[file.content_type]}"
    path.write_bytes(raw)

    job = HealthAnalysisJob(
        user_id=user_id,
        file_path=str(path),
        image_type=image_type,
        source=source,
        client_sha256=digest,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "status": job.status,
        "source": source,
        "image_type": image_type,
        "message": "已进入健康分析队列；AI 结果仅用于健康管理和风险提示，不作为诊断结论。",
    }


@router.get("/jobs/{job_id}")
def job_status(
    job_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    job = (
        db.query(HealthAnalysisJob)
        .filter(HealthAnalysisJob.id == job_id, HealthAnalysisJob.user_id == user_id)
        .first()
    )
    if not job:
        raise HTTPException(404, "job not found")
    return {
        "id": job.id,
        "status": job.status,
        "source": job.source,
        "image_type": job.image_type,
        "error": job.error,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }


@router.get("/records")
def records(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = (
        db.query(HealthRecord)
        .filter(HealthRecord.user_id == user_id)
        .order_by(HealthRecord.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": r.id,
            "source": r.source,
            "image_type": r.image_type,
            "summary": r.summary,
            "risk_level": r.risk_level,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/alerts")
def alerts(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = (
        db.query(HealthAlert)
        .filter(HealthAlert.user_id == user_id, HealthAlert.acknowledged.is_(False))
        .order_by(HealthAlert.created_at.desc())
        .all()
    )
    return [
        {"id": a.id, "severity": a.severity, "message": a.message, "created_at": a.created_at}
        for a in rows
    ]

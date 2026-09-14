import hashlib
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user_id
from app.db import get_db
from app.models import HealthAlert, HealthAnalysisJob, HealthRecord
from app.services.health_analysis import analyze_health_job
from app.services.health_facts import build_context
from app.services.health_ingest import classify_candidate
from app.services.health_service import validate_image_bytes
from app.services.weekly_health_report import get_current_report, generate_weekly_report
from app.services.wellness_service import generate_weekly_plan, get_current_plan

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
def gallery_preflight(data: GalleryPreflightIn, user_id: int = Depends(get_current_user_id)):
    """Classify gallery candidates locally from metadata/OCR; never calls the LLM."""
    results = []
    for candidate in data.candidates:
        result = classify_candidate(candidate.filename, candidate.ocr_text)
        results.append({"filename": candidate.filename, "image_type": result.image_type, "confidence": result.confidence, "reasons": list(result.reasons), "should_send_to_ai": result.should_send_to_ai})
    return {"user_id": user_id, "token_cost": 0, "results": results, "policy": "local_filter_first", "unknown_requires_user_confirmation": True}


@router.post("/upload")
async def upload_health_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    image_type: str = Form("unknown"),
    source: str = Form("gallery"),
    client_sha256: str | None = Form(None),
    ocr_text: str = Form(""),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    if file.content_type not in ALLOWED:
        raise HTTPException(400, "only JPG/PNG/WEBP images are supported")
    image_type = image_type if image_type in IMAGE_TYPES else "unknown"
    source = source if source in SOURCES else "file"
    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "file too large")
    try:
        validate_image_bytes(raw, file.content_type)
    except ValueError as exc:
        raise HTTPException(400, "invalid image payload") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if client_sha256 and client_sha256.lower() != digest:
        raise HTTPException(400, "image hash mismatch; please reselect the image")

    duplicate = (
        db.query(HealthAnalysisJob)
        .filter(HealthAnalysisJob.user_id == user_id, HealthAnalysisJob.client_sha256 == digest, HealthAnalysisJob.status.in_(["pending", "running", "completed"]))
        .order_by(HealthAnalysisJob.id.desc())
        .first()
    )
    if duplicate:
        return {"job_id": duplicate.id, "status": duplicate.status, "duplicate": True, "message": "这张图片已经提交过，无需重复上传。"}

    root = Path(settings.storage_dir) / str(user_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{uuid.uuid4().hex}{ALLOWED[file.content_type]}"
    path.write_bytes(raw)
    job = HealthAnalysisJob(user_id=user_id, file_path=str(path), image_type=image_type, source=source, client_sha256=digest, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(analyze_health_job, job.id, ocr_text[:12000])
    return {"job_id": job.id, "status": job.status, "source": source, "image_type": image_type, "message": "已进入健康分析队列；AI 结果仅用于健康管理和风险提示，不作为诊断结论。"}


@router.get("/jobs/{job_id}")
def job_status(job_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    job = db.query(HealthAnalysisJob).filter(HealthAnalysisJob.id == job_id, HealthAnalysisJob.user_id == user_id).first()
    if not job:
        raise HTTPException(404, "job not found")
    return {"id": job.id, "status": job.status, "source": job.source, "image_type": job.image_type, "error": job.error, "created_at": job.created_at, "completed_at": job.completed_at}


@router.get("/records")
def records(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = db.query(HealthRecord).filter(HealthRecord.user_id == user_id).order_by(HealthRecord.created_at.desc()).limit(100).all()
    return [{"id": r.id, "source": r.source, "image_type": r.image_type, "summary": r.summary, "risk_level": r.risk_level, "created_at": r.created_at} for r in rows]


@router.get("/facts")
def facts(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    context = build_context(db, user_id, days=14, max_facts=50)
    return {"facts": context.facts, "trends": context.trends}


@router.get("/trends")
def trends(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return {"trends": build_context(db, user_id, days=30, max_facts=100).trends}


@router.get("/alerts")
def alerts(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = db.query(HealthAlert).filter(HealthAlert.user_id == user_id, HealthAlert.acknowledged.is_(False)).order_by(HealthAlert.created_at.desc()).all()
    return [{"id": a.id, "severity": a.severity, "message": a.message, "created_at": a.created_at} for a in rows]


@router.get("/weekly-report")
def weekly_report(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    report = get_current_report(db, user_id)
    if not report:
        return {"status": "not_generated", "report": None}
    return {"status": report.status, "week_start": report.week_start, "report": json.loads(report.report_json), "updated_at": report.updated_at}


@router.get("/weekly-report/curves")
def weekly_report_curves(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    report = get_current_report(db, user_id)
    if not report:
        return {"status": "not_generated", "week_start": None, "curves": []}
    payload = json.loads(report.report_json)
    data = payload.get("data") or {}
    return {"status": report.status, "week_start": report.week_start, "curves": data.get("curves", []), "risk_counts": data.get("risk_counts", {}), "total_samples": data.get("total_samples", 0)}


@router.post("/weekly-report/generate")
async def weekly_report_generate(background_tasks: BackgroundTasks, force: bool = False, user_id: int = Depends(get_current_user_id)):
    background_tasks.add_task(_generate_weekly_report_task, user_id, force)
    return {"status": "processing", "message": "本周健康评估、曲线和调理方案正在生成。"}


async def _generate_weekly_report_task(user_id: int, force: bool) -> None:
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        await generate_weekly_report(db, user_id, force=force)
    finally:
        db.close()


@router.get("/weekly-plan")
def weekly_plan(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    plan = get_current_plan(db, user_id)
    if not plan:
        return {"status": "not_generated", "plan": None}
    return {"status": plan.status, "week_start": plan.week_start, "plan": json.loads(plan.plan_json), "updated_at": plan.updated_at}


@router.post("/weekly-plan/generate")
async def weekly_plan_generate(background_tasks: BackgroundTasks, force: bool = False, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    background_tasks.add_task(_generate_plan_task, user_id, force)
    return {"status": "processing", "message": "周健康计划正在生成。"}


async def _generate_plan_task(user_id: int, force: bool) -> None:
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        await generate_weekly_plan(db, user_id, force=force)
    finally:
        db.close()

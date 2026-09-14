from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import update

from app.db import SessionLocal
from app.models import AIUsage, HealthAlert, HealthAnalysisJob, HealthMetric, HealthRecord
from app.services.ai_gateway import AIRequest, AIGateway
from app.services.ai_provider import OpenAICompatibleProvider
from app.services.gemini_vision_provider import GeminiVisionProvider
from app.services.health_facts import build_context, compact_json
from app.services.health_prompt import build_health_analysis_prompt
from app.services.runtime_config import load_runtime_config


async def analyze_health_job(job_id: int, ocr_text: str = "") -> None:
    db = SessionLocal()
    try:
        claimed = db.execute(
            update(HealthAnalysisJob)
            .where(
                HealthAnalysisJob.id == job_id,
                HealthAnalysisJob.status.in_(["pending", "failed"]),
            )
            .values(status="running", error="", completed_at=None)
        ).rowcount
        db.commit()
        if not claimed:
            return

        job = db.query(HealthAnalysisJob).filter(HealthAnalysisJob.id == job_id).first()
        if not job:
            return

        config = load_runtime_config(db)
        context = build_context(db, job.user_id)
        messages = build_health_analysis_prompt(job.image_type, ocr_text, compact_json(context))
        gateway = AIGateway()

        if job.image_type in {"face", "tongue"}:
            gateway.register(GeminiVisionProvider(config.gemini_api_key, config.gemini_model), default=True)
            request_metadata = {
                "feature": "health_visual_analysis",
                "job_id": job.id,
                "image_path": job.file_path,
            }
        else:
            if not (config.ai_api_url and config.ai_api_key and config.ai_model):
                raise RuntimeError("AI provider is not configured")
            gateway.register(
                OpenAICompatibleProvider(config.ai_api_url, config.ai_api_key, config.ai_model),
                default=True,
            )
            request_metadata = {"feature": "health_image_analysis", "job_id": job.id}

        result = await gateway.chat(
            AIRequest(
                user_id=job.user_id,
                messages=messages,
                max_tokens=1600,
                temperature=0.1,
                metadata=request_metadata,
            )
        )
        payload = _parse_result(result.text)
        risk_level = payload.get("risk_level", "normal")
        if risk_level not in {"normal", "watch", "urgent"}:
            risk_level = "watch"

        image_quality = payload.get("image_quality", "acceptable")
        if image_quality not in {"good", "acceptable", "poor"}:
            image_quality = "acceptable"
        confidence = _clamp_confidence(payload.get("analysis_confidence", 0.0))
        if job.image_type in {"face", "tongue"}:
            if image_quality == "poor" or confidence < 0.5:
                risk_level = "watch" if risk_level == "urgent" else risk_level
            if image_quality == "poor":
                risk_level = "watch"

        record = HealthRecord(
            user_id=job.user_id,
            source=job.source,
            image_type=payload.get("image_type") or job.image_type,
            summary=str(payload.get("summary") or ""),
            risk_level=risk_level,
        )
        db.add(record)
        db.flush()

        if job.image_type in {"face", "tongue"}:
            db.add(HealthMetric(record_id=record.id, name="visual_image_quality", value=image_quality, unit=""))
            db.add(HealthMetric(record_id=record.id, name="visual_analysis_confidence", value=f"{confidence:.2f}", unit="ratio"))

        for observation in payload.get("observations") or []:
            if observation:
                db.add(
                    HealthMetric(
                        record_id=record.id,
                        name="visual_observation",
                        value=str(observation)[:128],
                        unit="",
                    )
                )

        for metric in payload.get("metrics") or []:
            if not isinstance(metric, dict) or not metric.get("name") or metric.get("value") is None:
                continue
            db.add(
                HealthMetric(
                    record_id=record.id,
                    name=str(metric["name"])[:64],
                    value=str(metric["value"])[:128],
                    unit=str(metric.get("unit") or "")[:32],
                )
            )

        for flag in payload.get("flags") or []:
            if not isinstance(flag, dict) or not flag.get("message"):
                continue
            severity = flag.get("severity") if flag.get("severity") in {"watch", "urgent"} else risk_level
            if job.image_type in {"face", "tongue"} and (image_quality == "poor" or confidence < 0.5):
                severity = "watch"
            if severity in {"watch", "urgent"}:
                db.add(
                    HealthAlert(
                        user_id=job.user_id,
                        record_id=record.id,
                        severity=severity,
                        message=str(flag["message"])[:2000],
                    )
                )

        if risk_level == "urgent" and not (payload.get("flags") or []):
            db.add(
                HealthAlert(
                    user_id=job.user_id,
                    record_id=record.id,
                    severity="urgent",
                    message="健康图片分析提示存在需要尽快关注的风险，请结合实际症状及时联系专业医疗人员。",
                )
            )

        db.add(
            AIUsage(
                user_id=job.user_id,
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                request_id=result.request_id,
            )
        )
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        job = db.query(HealthAnalysisJob).filter(HealthAnalysisJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = "健康分析暂时失败，请稍后重试。"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def _clamp_confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _parse_result(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("health AI returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("health AI returned a non-object JSON result")
    return payload

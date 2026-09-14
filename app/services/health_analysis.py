from __future__ import annotations

import json
from datetime import datetime

from app.db import SessionLocal
from app.models import AIUsage, HealthAlert, HealthAnalysisJob, HealthMetric, HealthRecord
from app.services.ai_gateway import AIRequest, AIGateway
from app.services.ai_provider import OpenAICompatibleProvider
from app.services.health_facts import build_context, compact_json
from app.services.health_prompt import build_health_analysis_prompt
from app.services.runtime_config import load_runtime_config


async def analyze_health_job(job_id: int, ocr_text: str = "") -> None:
    db = SessionLocal()
    try:
        job = db.query(HealthAnalysisJob).filter(HealthAnalysisJob.id == job_id).first()
        if not job or job.status == "completed":
            return
        job.status = "running"
        job.error = ""
        db.commit()

        config = load_runtime_config(db)
        if not (config.ai_api_url and config.ai_api_key and config.ai_model):
            raise RuntimeError("AI health analysis is not configured")

        context = build_context(db, job.user_id)
        messages = build_health_analysis_prompt(job.image_type, ocr_text, compact_json(context))
        gateway = AIGateway()
        gateway.register(
            OpenAICompatibleProvider(config.ai_api_url, config.ai_api_key, config.ai_model),
            default=True,
        )
        result = await gateway.chat(
            AIRequest(
                user_id=job.user_id,
                messages=messages,
                max_tokens=1600,
                temperature=0.1,
                metadata={"feature": "health_image_analysis", "job_id": job.id},
            )
        )
        payload = _parse_result(result.text)
        risk_level = payload.get("risk_level", "normal")
        if risk_level not in {"normal", "watch", "urgent"}:
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
        job.completed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.query(HealthAnalysisJob).filter(HealthAnalysisJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(exc)[:2000]
            job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


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

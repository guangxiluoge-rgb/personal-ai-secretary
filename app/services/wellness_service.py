from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import AIUsage, WeeklyWellnessPlan
from app.services.ai_gateway import AIGateway, AIRequest
from app.services.ai_provider import OpenAICompatibleProvider
from app.services.health_facts import build_context, compact_json
from app.services.runtime_config import load_runtime_config


WEEKLY_SCHEMA = {
    "week_start": "YYYY-MM-DD",
    "summary": "string",
    "nutrition": ["string"],
    "exercise": ["string"],
    "sleep": ["string"],
    "recovery": ["string"],
    "mindfulness": ["string"],
    "body_care": ["string"],
    "music_aromatherapy": ["string"],
    "safety_notes": ["string"],
}


def week_start(now: datetime | None = None) -> datetime:
    now = now or datetime.utcnow()
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def context_hash(context_json: str) -> str:
    return hashlib.sha256(context_json.encode("utf-8")).hexdigest()


def get_current_plan(db: Session, user_id: int) -> WeeklyWellnessPlan | None:
    return (
        db.query(WeeklyWellnessPlan)
        .filter(
            WeeklyWellnessPlan.user_id == user_id,
            WeeklyWellnessPlan.week_start == week_start(),
            WeeklyWellnessPlan.status == "active",
        )
        .first()
    )


async def generate_weekly_plan(db: Session, user_id: int, force: bool = False) -> WeeklyWellnessPlan:
    current = get_current_plan(db, user_id)
    context = compact_json(build_context(db, user_id, days=14, max_facts=50), max_chars=4500)
    digest = context_hash(context)
    if current and not force and current.source_context_hash == digest:
        return current

    config = load_runtime_config(db)
    if not (config.antfu_api_url and config.antfu_api_key and config.antfu_model):
        raise RuntimeError("AI health analysis is not configured")

    prompt = _build_prompt(context)
    gateway = AIGateway()
    gateway.register(OpenAICompatibleProvider(config.antfu_api_url, config.antfu_api_key, config.antfu_model), default=True)
    result = await gateway.chat(
        AIRequest(
            user_id=user_id,
            messages=prompt,
            max_tokens=1200,
            temperature=0.2,
            metadata={"feature": "weekly_wellness_plan"},
        )
    )
    payload = _parse_result(result.text)
    payload = _normalize_plan(payload)

    if current:
        current.plan_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        current.source_context_hash = digest
        current.updated_at = datetime.utcnow()
    else:
        current = WeeklyWellnessPlan(
            user_id=user_id,
            week_start=week_start(),
            plan_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            source_context_hash=digest,
            status="active",
        )
        db.add(current)

    db.add(
        AIUsage(
            user_id=user_id,
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            request_id=result.request_id,
        )
    )
    db.commit()
    db.refresh(current)
    return current


def _build_prompt(context_json: str) -> list[dict[str, str]]:
    system = (
        "你是健康管理计划生成助手。只根据提供的结构化健康事实和趋势制定一周生活方式计划。"
        "不得诊断疾病，不开具处方，不把生活方式建议描述成医疗结论。"
        "输出严格 JSON；数据不足时使用保守、低风险建议。"
    )
    user = {
        "task": "生成一周健康管理计划，覆盖饮食/食疗、运动、睡眠恢复、冥想、泡澡或泡脚、按摩或拉伸、芳香疗法、音乐疗法，并给出安全注意事项。",
        "health_context": json.loads(context_json),
        "output_schema": WEEKLY_SCHEMA,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False, separators=(",", ":"))},
    ]


def _parse_result(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("wellness AI returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("wellness AI returned a non-object JSON result")
    return payload


def _normalize_plan(payload: dict) -> dict:
    result = {}
    for key, default in WEEKLY_SCHEMA.items():
        value = payload.get(key, default)
        if isinstance(default, list):
            if not isinstance(value, list):
                value = []
            value = [str(item)[:500] for item in value[:10] if item is not None]
        else:
            value = str(value)[:1000]
        result[key] = value
    result["week_start"] = week_start().date().isoformat()
    return result

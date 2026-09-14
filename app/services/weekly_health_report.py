from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import AIUsage, WeeklyHealthReport
from app.services.ai_gateway import AIGateway, AIRequest
from app.services.ai_provider import OpenAICompatibleProvider
from app.services.health_facts import _numeric_value
from app.services.runtime_config import load_runtime_config

REPORT_DOMAINS = (
    "diet",
    "rest",
    "sleep",
    "energy",
    "emotion",
    "exercise",
    "nutrition",
    "other",
)


def week_start(now: datetime | None = None) -> datetime:
    now = now or datetime.utcnow()
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def get_current_report(db: Session, user_id: int) -> WeeklyHealthReport | None:
    return (
        db.query(WeeklyHealthReport)
        .filter(
            WeeklyHealthReport.user_id == user_id,
            WeeklyHealthReport.week_start == week_start(),
            WeeklyHealthReport.status == "active",
        )
        .first()
    )


def build_weekly_aggregation(db: Session, user_id: int, start: datetime | None = None) -> dict:
    from app.models import HealthMetric, HealthRecord

    start = start or week_start()
    end = start + timedelta(days=7)
    rows = (
        db.query(HealthMetric, HealthRecord)
        .join(HealthRecord, HealthMetric.record_id == HealthRecord.id)
        .filter(
            HealthRecord.user_id == user_id,
            HealthMetric.created_at >= start,
            HealthMetric.created_at < end,
        )
        .order_by(HealthMetric.created_at.asc())
        .all()
    )

    series: dict[str, list[dict]] = defaultdict(list)
    for metric, record in rows:
        value = _numeric_value(metric.value)
        series[metric.name].append(
            {
                "recorded_at": metric.created_at.isoformat(),
                "value": value,
                "raw_value": metric.value,
                "unit": metric.unit,
                "source": record.image_type or record.source,
            }
        )

    curves = []
    for name, points in sorted(series.items()):
        numeric_points = [p for p in points if p["value"] is not None]
        curves.append(
            {
                "name": name,
                "unit": next((p["unit"] for p in points if p["unit"]), ""),
                "points": points,
                "numeric": bool(numeric_points),
                "samples": len(points),
            }
        )

    risk_counts = defaultdict(int)
    records = {}
    for _, record in rows:
        records[record.id] = record
        risk_counts[record.risk_level] += 1

    return {
        "week_start": start.date().isoformat(),
        "week_end": (end - timedelta(seconds=1)).date().isoformat(),
        "total_samples": len(rows),
        "metric_count": len(curves),
        "curves": curves,
        "risk_counts": dict(risk_counts),
        "record_count": len(records),
    }


def _deterministic_recommendations(aggregation: dict) -> dict:
    recommendations = {domain: [] for domain in REPORT_DOMAINS}
    coverage = aggregation["metric_count"]
    recommendations["diet"].append("保持规律、均衡、食材多样的饮食；根据实际饮食记录逐步调整，不把视觉分析当作饮食诊断。")
    recommendations["rest"].append("安排固定放松时段，避免连续高负荷工作；结合精力和恢复趋势调整当天负荷。")
    recommendations["sleep"].append("尽量固定睡眠时间，睡前减少强刺激活动，并结合睡眠趋势持续调整。")
    recommendations["energy"].append("按当天精力水平分级安排活动：状态差时优先低强度活动与恢复。")
    recommendations["emotion"].append("每天安排短时情绪整理、呼吸或正念练习；数据不足时不做确定性情绪判断。")
    recommendations["exercise"].append("保持规律运动，优先稳定频率而非一次性高强度；出现明显不适时暂停并寻求专业建议。")
    recommendations["nutrition"].append("优先从日常食物获取均衡营养；营养补充需结合饮食、用药和专业意见，不自动推荐高剂量补充剂。")
    recommendations["other"].append("优先补齐连续可比的睡眠、活动、精力和情绪记录，提高下周趋势判断质量。")

    risk_counts = aggregation.get("risk_counts", {})
    if risk_counts.get("urgent", 0):
        recommendations["other"].insert(0, "本周存在高风险健康记录：不要仅依据周报处理，结合实际症状尽快联系专业医疗人员。")
    elif risk_counts.get("watch", 0):
        recommendations["other"].insert(0, "本周存在需要关注的健康记录，建议复查相关指标并结合实际症状观察变化。")

    if coverage == 0:
        recommendations["other"] = ["本周暂无结构化健康数据，先完成健康数据采集，再进行有意义的周度评估。"]
    return recommendations


def _report_hash(aggregation: dict) -> str:
    payload = json.dumps(aggregation, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_prompt(aggregation: dict, baseline: dict) -> list[dict[str, str]]:
    system = (
        "你是健康管理周报助手。根据结构化健康数据生成保守的生活方式评估和调理建议。"
        "不得诊断疾病、开药或给出确定的临床结论。"
        "只能使用输入中的数据；数据不足时明确写出数据不足。"
        "输出严格 JSON。"
    )
    schema = {
        "summary": "本周总体状态",
        "evaluation": [],
        "diet": [],
        "rest": [],
        "sleep": [],
        "energy": [],
        "emotion": [],
        "exercise": [],
        "nutrition": [],
        "other": [],
        "safety_notes": [],
    }
    user = {
        "task": "综合本周全部健康参数曲线和风险记录，形成周度评估与可执行建议。优先指出趋势而不是孤立数值。",
        "aggregation": aggregation,
        "baseline": baseline,
        "output_schema": schema,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False, separators=(",", ":"))},
    ]


async def generate_weekly_report(db: Session, user_id: int, force: bool = False) -> WeeklyHealthReport:
    current = get_current_report(db, user_id)
    aggregation = build_weekly_aggregation(db, user_id)
    digest = _report_hash(aggregation)
    if current and not force and current.source_context_hash == digest:
        return current

    baseline = _deterministic_recommendations(aggregation)
    payload = {
        "week_start": aggregation["week_start"],
        "week_end": aggregation["week_end"],
        "data": aggregation,
        "summary": "本周健康数据周报。",
        "evaluation": [],
        "recommendations": baseline,
        "safety_notes": ["本周报用于健康管理和趋势观察，不作为疾病诊断。"],
        "source_context_hash": digest,
        "generated_at": datetime.utcnow().isoformat(),
    }

    config = load_runtime_config(db)
    if config.ai_api_url and config.ai_api_key and config.ai_model and (force or aggregation["metric_count"] > 0):
        gateway = AIGateway()
        gateway.register(OpenAICompatibleProvider(config.ai_api_url, config.ai_api_key, config.ai_model), default=True)
        result = await gateway.chat(
            AIRequest(
                user_id=user_id,
                messages=_build_prompt(aggregation, baseline),
                max_tokens=1800,
                temperature=0.2,
                metadata={"feature": "weekly_health_report"},
            )
        )
        ai_payload = _parse_result(result.text)
        payload["summary"] = str(ai_payload.get("summary") or payload["summary"])[:2000]
        payload["evaluation"] = [str(x)[:800] for x in (ai_payload.get("evaluation") or [])[:12]]
        for domain in REPORT_DOMAINS:
            values = ai_payload.get(domain)
            if isinstance(values, list) and values:
                payload["recommendations"][domain] = [str(x)[:800] for x in values[:10]]
        safety = ai_payload.get("safety_notes")
        if isinstance(safety, list) and safety:
            payload["safety_notes"] = [str(x)[:800] for x in safety[:10]]
        db.add(AIUsage(user_id=user_id, provider=result.provider, model=result.model, input_tokens=result.input_tokens, output_tokens=result.output_tokens, request_id=result.request_id))

    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if current:
        current.report_json = encoded
        current.source_context_hash = digest
        current.updated_at = datetime.utcnow()
    else:
        current = WeeklyHealthReport(
            user_id=user_id,
            week_start=week_start(),
            report_json=encoded,
            source_context_hash=digest,
            status="active",
        )
        db.add(current)
    db.commit()
    db.refresh(current)
    return current


def _parse_result(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("weekly health report AI returned a non-object JSON result")
    return payload

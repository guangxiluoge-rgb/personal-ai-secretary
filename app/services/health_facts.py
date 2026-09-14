from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import HealthMetric, HealthRecord


@dataclass(frozen=True)
class HealthContext:
    facts: list[dict]
    trends: list[dict]


def build_context(db: Session, user_id: int, days: int = 7, max_facts: int = 40) -> HealthContext:
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(HealthMetric, HealthRecord)
        .join(HealthRecord, HealthMetric.record_id == HealthRecord.id)
        .filter(HealthRecord.user_id == user_id, HealthMetric.created_at >= since)
        .order_by(HealthMetric.created_at.desc())
        .limit(max_facts)
        .all()
    )
    facts = [
        {
            "name": metric.name,
            "value": metric.value,
            "unit": metric.unit,
            "recorded_at": metric.created_at.isoformat(),
            "source": record.image_type or record.source,
        }
        for metric, record in rows
    ]
    return HealthContext(facts=facts, trends=_derive_trends(facts))


def _derive_trends(facts: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for fact in facts:
        grouped.setdefault(fact["name"], []).append(fact)

    trends = []
    for name, items in grouped.items():
        if len(items) < 2:
            continue
        values = []
        for item in reversed(items):
            try:
                values.append(float(item["value"]))
            except (TypeError, ValueError):
                values = []
                break
        if len(values) >= 2 and values[0] != 0:
            change_pct = round((values[-1] - values[0]) / abs(values[0]) * 100, 1)
            trends.append({"name": name, "change_pct": change_pct, "samples": len(values)})
    return trends


def compact_json(context: HealthContext, max_chars: int = 5000) -> str:
    payload = {"facts": context.facts, "trends": context.trends}
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text[:max_chars]

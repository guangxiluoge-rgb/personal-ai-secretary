from __future__ import annotations

import json
import re
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


def _numeric_value(value: object) -> float | None:
    """Extract the leading numeric value while allowing common units such as bpm or mmHg."""
    match = re.match(r"\s*([-+]?\d+(?:\.\d+)?)\b", str(value))
    return float(match.group(1)) if match else None


def _derive_trends(facts: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for fact in facts:
        grouped.setdefault(fact["name"], []).append(fact)

    trends = []
    for name, items in grouped.items():
        if len(items) < 2:
            continue
        values = [_numeric_value(item["value"]) for item in reversed(items)]
        if any(value is None for value in values):
            continue
        first, last = values[0], values[-1]
        if first == 0:
            continue
        change_pct = round((last - first) / abs(first) * 100, 1)
        trends.append({"name": name, "change_pct": change_pct, "samples": len(values)})
    return trends[:20]


def compact_json(context: HealthContext, max_chars: int = 5000) -> str:
    payload = {"facts": context.facts, "trends": context.trends}
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(text) <= max_chars:
        return text
    bounded = {"facts": [], "trends": context.trends}
    for fact in context.facts:
        candidate = {"facts": bounded["facts"] + [fact], "trends": bounded["trends"]}
        encoded = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > max_chars:
            break
        bounded["facts"].append(fact)
    return json.dumps(bounded, ensure_ascii=False, separators=(",", ":"))

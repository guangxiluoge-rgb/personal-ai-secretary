from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import WeeklyHealthReport
from app.services.weekly_health_report import week_start


def list_history(db: Session, user_id: int, limit: int = 12) -> list[WeeklyHealthReport]:
    limit = max(1, min(limit, 52))
    return (
        db.query(WeeklyHealthReport)
        .filter(WeeklyHealthReport.user_id == user_id, WeeklyHealthReport.status == "active")
        .order_by(WeeklyHealthReport.week_start.desc())
        .limit(limit)
        .all()
    )


def get_history_report(db: Session, user_id: int, start_date: str) -> WeeklyHealthReport | None:
    try:
        target = datetime.fromisoformat(start_date).replace(hour=0, minute=0, second=0, microsecond=0)
    except ValueError as exc:
        raise ValueError("invalid week_start; expected YYYY-MM-DD") from exc
    return (
        db.query(WeeklyHealthReport)
        .filter(
            WeeklyHealthReport.user_id == user_id,
            WeeklyHealthReport.week_start == target,
            WeeklyHealthReport.status == "active",
        )
        .first()
    )


def four_week_metrics(db: Session, user_id: int, anchor: datetime | None = None) -> dict:
    anchor = week_start(anchor)
    start = anchor - timedelta(weeks=3)
    reports = (
        db.query(WeeklyHealthReport)
        .filter(
            WeeklyHealthReport.user_id == user_id,
            WeeklyHealthReport.status == "active",
            WeeklyHealthReport.week_start >= start,
            WeeklyHealthReport.week_start <= anchor,
        )
        .order_by(WeeklyHealthReport.week_start.asc())
        .all()
    )

    metric_points: dict[str, list[dict]] = defaultdict(list)
    week_summary: list[dict] = []
    for report in reports:
        payload = json.loads(report.report_json)
        data = payload.get("data") or {}
        week_summary.append(
            {
                "week_start": report.week_start.date().isoformat(),
                "total_samples": data.get("total_samples", 0),
                "metric_count": data.get("metric_count", 0),
                "risk_counts": data.get("risk_counts", {}),
            }
        )
        for curve in data.get("curves", []):
            values = [p.get("value") for p in curve.get("points", []) if isinstance(p.get("value"), (int, float))]
            if not values:
                continue
            average = round(sum(values) / len(values), 2)
            metric_points[curve.get("name", "unknown")].append(
                {
                    "week_start": report.week_start.date().isoformat(),
                    "average": average,
                    "latest": values[-1],
                    "samples": len(values),
                    "unit": curve.get("unit", ""),
                }
            )

    metrics = []
    for name, points in sorted(metric_points.items()):
        first = points[0]["average"]
        last = points[-1]["average"]
        change_pct = None if first == 0 else round((last - first) / abs(first) * 100, 1)
        metrics.append({"name": name, "unit": points[-1].get("unit", ""), "points": points, "change_pct": change_pct})

    return {
        "anchor_week_start": anchor.date().isoformat(),
        "weeks": week_summary,
        "metrics": metrics,
    }

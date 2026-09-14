from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import WeeklyHealthReport
from app.services.weekly_health_report import week_start


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _quarter_start(value: datetime) -> datetime:
    month = ((value.month - 1) // 3) * 3 + 1
    return value.replace(month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def _periods(anchor: datetime, months: int) -> list[datetime]:
    current = _month_start(anchor)
    result: list[datetime] = []
    for offset in range(months - 1, -1, -1):
        month_index = current.month - 1 - offset
        year = current.year + month_index // 12
        month = month_index % 12 + 1
        result.append(current.replace(year=year, month=month))
    return result


def _risk_level_counts(reports: list[WeeklyHealthReport]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for report in reports:
        payload = json.loads(report.report_json)
        for level, count in (payload.get("data", {}).get("risk_counts", {}) or {}).items():
            counts[level] += int(count or 0)
    return dict(counts)


def _aggregate_periods(db: Session, user_id: int, starts: list[datetime], period: str) -> list[dict]:
    if not starts:
        return []
    lower = starts[0]
    if period == "month":
        next_year = starts[-1].year + (1 if starts[-1].month == 12 else 0)
        next_month = 1 if starts[-1].month == 12 else starts[-1].month + 1
        upper = starts[-1].replace(year=next_year, month=next_month)
    else:
        upper = starts[-1] + timedelta(days=92)

    reports = (
        db.query(WeeklyHealthReport)
        .filter(
            WeeklyHealthReport.user_id == user_id,
            WeeklyHealthReport.status == "active",
            WeeklyHealthReport.week_start >= lower,
            WeeklyHealthReport.week_start < upper,
        )
        .order_by(WeeklyHealthReport.week_start.asc())
        .all()
    )

    buckets: dict[datetime, list[WeeklyHealthReport]] = defaultdict(list)
    for report in reports:
        key = _month_start(report.week_start) if period == "month" else _quarter_start(report.week_start)
        buckets[key].append(report)

    output = []
    for start in starts:
        bucket = buckets.get(start, [])
        metric_values: dict[str, list[float]] = defaultdict(list)
        units: dict[str, str] = {}
        samples = 0
        for report in bucket:
            data = (json.loads(report.report_json).get("data") or {})
            samples += int(data.get("total_samples", 0) or 0)
            for curve in data.get("curves", []):
                units[curve.get("name", "unknown")] = curve.get("unit", "")
                for point in curve.get("points", []):
                    value = point.get("value")
                    if isinstance(value, (int, float)):
                        metric_values[curve.get("name", "unknown")].append(float(value))
        metrics = []
        for name, values in sorted(metric_values.items()):
            if not values:
                continue
            metrics.append({
                "name": name,
                "unit": units.get(name, ""),
                "average": round(sum(values) / len(values), 2),
                "latest": values[-1],
                "samples": len(values),
            })
        output.append({
            "period_start": start.date().isoformat(),
            "report_count": len(bucket),
            "sample_count": samples,
            "risk_counts": _risk_level_counts(bucket),
            "metrics": metrics,
        })
    return output


def monthly_profile(db: Session, user_id: int, anchor: datetime | None = None, months: int = 6) -> dict:
    anchor = week_start(anchor)
    months = max(1, min(months, 12))
    periods = _periods(anchor, months)
    return {"period": "month", "months": _aggregate_periods(db, user_id, periods, "month")}


def quarterly_profile(db: Session, user_id: int, anchor: datetime | None = None, quarters: int = 4) -> dict:
    anchor = week_start(anchor)
    current = _quarter_start(anchor)
    starts: list[datetime] = []
    for offset in range(quarters - 1, -1, -1):
        index = (current.year * 4 + (current.month - 1) // 3) - offset
        year, quarter_index = divmod(index, 4)
        starts.append(current.replace(year=year, month=quarter_index * 3 + 1, day=1))
    return {"period": "quarter", "quarters": _aggregate_periods(db, user_id, starts, "quarter")}

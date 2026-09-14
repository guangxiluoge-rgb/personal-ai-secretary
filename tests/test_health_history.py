import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.health_history import four_week_metrics, get_history_report


def _report(week_start: datetime, metric_name: str = "心率"):
    payload = {
        "data": {
            "total_samples": 2,
            "metric_count": 1,
            "risk_counts": {"normal": 2},
            "curves": [{"name": metric_name, "unit": "bpm", "points": [{"value": 60}, {"value": 70}]}],
        }
    }
    return SimpleNamespace(week_start=week_start, status="active", report_json=json.dumps(payload))


def test_four_week_metrics_groups_weekly_averages():
    anchor = datetime(2026, 9, 14)
    rows = [_report(anchor - timedelta(weeks=i)) for i in (3, 2, 1, 0)]
    query = MagicMock()
    query.filter.return_value.order_by.return_value.all.return_value = list(reversed(rows))
    db = MagicMock()
    db.query.return_value = query

    result = four_week_metrics(db, user_id=7, anchor=anchor)
    assert result["anchor_week_start"] == "2026-09-14"
    assert len(result["weeks"]) == 4
    assert result["metrics"][0]["name"] == "心率"
    assert result["metrics"][0]["points"][0]["average"] == 65


def test_get_history_report_rejects_invalid_date():
    db = MagicMock()
    try:
        get_history_report(db, user_id=1, start_date="not-a-date")
    except ValueError as exc:
        assert "YYYY-MM-DD" in str(exc)
    else:
        raise AssertionError("invalid date must raise ValueError")

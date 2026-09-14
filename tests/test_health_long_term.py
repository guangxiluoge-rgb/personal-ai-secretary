import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.health_long_term import monthly_profile, quarterly_profile


def _report(start: datetime, value: float):
    payload = {"data": {"total_samples": 3, "risk_counts": {"normal": 3}, "curves": [{"name": "心率", "unit": "bpm", "points": [{"value": value}, {"value": value + 4}]}]}}
    return SimpleNamespace(week_start=start, status="active", report_json=json.dumps(payload))


def test_monthly_profile_groups_reports_into_months():
    rows = [_report(datetime(2026, 8, 3), 60), _report(datetime(2026, 8, 10), 64), _report(datetime(2026, 9, 7), 70)]
    query = MagicMock()
    query.filter.return_value.order_by.return_value.all.return_value = rows
    db = MagicMock()
    db.query.return_value = query

    result = monthly_profile(db, 1, anchor=datetime(2026, 9, 14), months=2)
    assert result["months"][0]["period_start"] == "2026-08-01"
    assert result["months"][0]["report_count"] == 2
    assert result["months"][1]["report_count"] == 1
    assert result["months"][0]["metrics"][0]["average"] == 64


def test_quarterly_profile_groups_reports_into_quarters():
    rows = [_report(datetime(2026, 3, 30), 60), _report(datetime(2026, 4, 6), 70), _report(datetime(2026, 8, 3), 80)]
    query = MagicMock()
    query.filter.return_value.order_by.return_value.all.return_value = rows
    db = MagicMock()
    db.query.return_value = query

    result = quarterly_profile(db, 1, anchor=datetime(2026, 9, 14), quarters=3)
    starts = [x["period_start"] for x in result["quarters"]]
    assert starts == ["2026-01-01", "2026-04-01", "2026-07-01"]
    assert result["quarters"][1]["report_count"] == 1
    assert result["quarters"][2]["report_count"] == 1

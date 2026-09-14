from app.services.weekly_health_report import _deterministic_recommendations, _report_hash, week_start


def test_week_start_is_monday():
    monday = week_start()
    assert monday.weekday() == 0
    assert monday.hour == 0
    assert monday.minute == 0


def test_report_hash_changes_with_curve_data():
    first = {"week_start": "2026-09-14", "curves": [{"name": "sleep", "points": [7, 8]}]}
    second = {"week_start": "2026-09-14", "curves": [{"name": "sleep", "points": [7, 9]}]}
    assert _report_hash(first) != _report_hash(second)


def test_deterministic_recommendations_cover_requested_domains():
    report = _deterministic_recommendations(
        {
            "metric_count": 4,
            "risk_counts": {"normal": 5},
            "curves": [],
        }
    )
    assert set(report) == {"diet", "rest", "sleep", "energy", "emotion", "exercise", "nutrition", "other"}
    assert all(report[key] for key in report)


def test_urgent_risk_is_escalated_in_safety_recommendations():
    report = _deterministic_recommendations(
        {
            "metric_count": 2,
            "risk_counts": {"urgent": 1},
            "curves": [],
        }
    )
    assert "高风险" in report["other"][0]

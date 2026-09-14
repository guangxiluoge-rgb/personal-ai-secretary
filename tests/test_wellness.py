from datetime import datetime

from app.services.wellness_service import _normalize_plan, context_hash, week_start


def test_week_start_is_monday_midnight():
    value = week_start(datetime(2026, 9, 16, 14, 30))
    assert value == datetime(2026, 9, 14, 0, 0)


def test_context_hash_is_stable():
    assert context_hash('{"facts":[]}') == context_hash('{"facts":[]}')
    assert context_hash('{"facts":[]}') != context_hash('{"facts":[1]}')


def test_normalize_plan_bounds_lists_and_forces_week():
    payload = _normalize_plan({"summary": "ok", "nutrition": list(range(30)), "unknown": "ignored"})
    assert payload["week_start"]
    assert len(payload["nutrition"]) == 10
    assert payload["summary"] == "ok"
    assert "unknown" not in payload
    assert payload["exercise"] == []

from app.services.health_facts import HealthContext, _derive_trends, compact_json
from app.services.health_ingest import classify_candidate
from app.services.health_service import validate_image_bytes


def test_wearable_candidate_is_local_and_token_free():
    result = classify_candidate("Apple Watch Sleep.png", "深睡 2小时30分 心率 68")
    assert result.image_type == "wearable"
    assert result.should_send_to_ai is True


def test_ambiguous_candidate_requires_confirmation():
    result = classify_candidate("health report.png", "血糖 舌象 舌苔")
    assert result.image_type == "unknown"
    assert result.should_send_to_ai is False


def test_numeric_trends_ignore_units_embedded_in_values():
    facts = [
        {"name": "heart_rate", "value": "60", "unit": "bpm"},
        {"name": "heart_rate", "value": "66", "unit": "bpm"},
        {"name": "sleep", "value": "7h", "unit": "hour"},
        {"name": "sleep", "value": "8h", "unit": "hour"},
    ]
    trends = _derive_trends(facts)
    assert {item["name"] for item in trends} == {"heart_rate"}
    assert trends[0]["change_pct"] == 10.0


def test_compact_json_never_returns_broken_json():
    context = HealthContext(
        facts=[{"name": "heart_rate", "value": str(i), "unit": "bpm"} for i in range(40)],
        trends=[{"name": "heart_rate", "change_pct": 5.0, "samples": 40}],
    )
    import json
    payload = json.loads(compact_json(context, max_chars=300))
    assert isinstance(payload["facts"], list)
    assert isinstance(payload["trends"], list)


def test_image_signature_validation_accepts_supported_formats():
    validate_image_bytes(b"\xff\xd8\xffphoto", "image/jpeg")
    validate_image_bytes(b"\x89PNG\r\n\x1a\npayload", "image/png")
    validate_image_bytes(b"RIFF1234WEBPpayload", "image/webp")


def test_image_signature_validation_rejects_mismatched_payload():
    try:
        validate_image_bytes(b"not an image", "image/png")
    except ValueError as exc:
        assert "do not match" in str(exc)
    else:
        raise AssertionError("mismatched image payload was accepted")

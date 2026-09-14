from app.services.gemini_vision_provider import _extract_output_text, _mime_type


def test_gemini_mime_type_mapping():
    assert _mime_type(".jpg") == "image/jpeg"
    assert _mime_type(".png") == "image/png"
    assert _mime_type(".webp") == "image/webp"


def test_gemini_extracts_output_text():
    data = {
        "id": "int_test",
        "steps": [
            {"type": "model_output", "content": [{"type": "text", "text": "{\"risk_level\":\"normal\"}"}]}
        ],
    }
    assert _extract_output_text(data) == '{"risk_level":"normal"}'


def test_gemini_prefers_output_text():
    data = {
        "output_text": "{\"risk_level\":\"watch\"}",
        "steps": [{"content": [{"type": "text", "text": "ignored"}]}],
    }
    assert _extract_output_text(data) == '{"risk_level":"watch"}'

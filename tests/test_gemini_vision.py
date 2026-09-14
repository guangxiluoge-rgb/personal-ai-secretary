import asyncio

import pytest

from app.services.ai_gateway import AIRequest
from app.services.gemini_vision_provider import (
    GeminiVisionProvider,
    _extract_output_text,
    _mime_type,
    _response_schema,
)


def test_gemini_default_model_and_mime_type_mapping():
    provider = GeminiVisionProvider("test-key")
    assert provider.model == "gemini-3.8-flash"
    assert _mime_type(".jpg") == "image/jpeg"
    assert _mime_type(".png") == "image/png"
    assert _mime_type(".webp") == "image/webp"
    assert _mime_type(".unknown") == "image/jpeg"


def test_gemini_structured_output_schema_has_health_fields():
    schema = _response_schema()
    assert {"image_type", "summary", "risk_level", "observations", "metrics", "flags"} <= set(schema["required"])
    assert schema["properties"]["risk_level"]["enum"] == ["normal", "watch", "urgent"]


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


def test_gemini_requires_configuration():
    request = AIRequest(user_id=1, messages=[], metadata={"image_path": "/tmp/nope.jpg"})
    provider = GeminiVisionProvider("")
    with pytest.raises(RuntimeError, match="not configured"):
        asyncio.run(provider.chat(request))

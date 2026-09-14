from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import httpx

from app.services.ai_gateway import AIProvider, AIRequest, AIResponse


class GeminiVisionProvider(AIProvider):
    name = "gemini_vision"

    def __init__(self, api_key: str, model: str = "gemini-3.8-flash"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/interactions"

    async def chat(self, request: AIRequest) -> AIResponse:
        image_path = str((request.metadata or {}).get("image_path") or "")
        if not self.api_key or not self.model:
            raise RuntimeError("Gemini vision provider is not configured")
        if not image_path:
            raise RuntimeError("Gemini vision requires metadata.image_path")

        path = Path(image_path)
        if not path.is_file():
            raise RuntimeError("health image file is missing")
        raw = path.read_bytes()
        if len(raw) > 20 * 1024 * 1024:
            raise RuntimeError("health image is too large for inline Gemini vision input")

        mime_type = _mime_type(path.suffix.lower())
        instruction = "\n".join(str(item.get("content") or "") for item in request.messages)
        input_items = [
            {"type": "text", "text": instruction},
            {
                "type": "image",
                "data": base64.b64encode(raw).decode("ascii"),
                "mime_type": mime_type,
            },
        ]
        payload = {
            "model": request.model or self.model,
            "input": input_items,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": _response_schema(),
            },
        }
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    response = await client.post(self.endpoint, json=payload, headers=headers)
                if _is_retryable_status(response.status_code):
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                response.raise_for_status()
                data = response.json()
                break
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt >= 2:
                    raise RuntimeError("Gemini vision request failed after retries")
                await asyncio.sleep(0.5 * (2**attempt))
        else:
            raise RuntimeError("Gemini vision request failed after retries")

        text = _extract_output_text(data)
        usage = data.get("usage") or {}
        return AIResponse(
            text=text,
            provider=self.name,
            model=payload["model"],
            input_tokens=int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            request_id=data.get("id"),
        )


def _is_retryable_status(status_code: int) -> bool:
    return status_code in {408, 429} or status_code >= 500


def _mime_type(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".heif": "image/heif",
    }.get(suffix, "image/jpeg")


def _extract_output_text(data: dict) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    for step in reversed(data.get("steps") or []):
        for block in reversed(step.get("content") or []):
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                return block["text"]
    raise RuntimeError("Gemini vision returned no text output")


def _response_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "image_type": {"type": "string"},
            "image_quality": {"type": "string", "enum": ["good", "acceptable", "poor"]},
            "analysis_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "summary": {"type": "string"},
            "risk_level": {"type": "string", "enum": ["normal", "watch", "urgent"]},
            "observations": {"type": "array", "items": {"type": "string"}},
            "metrics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                        "unit": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["name", "value", "unit", "confidence"],
                },
            },
            "flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["watch", "urgent"]},
                        "message": {"type": "string"},
                    },
                    "required": ["severity", "message"],
                },
            },
        },
        "required": ["image_type", "image_quality", "analysis_confidence", "summary", "risk_level", "observations", "metrics", "flags"],
    }

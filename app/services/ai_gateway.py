from dataclasses import dataclass
from typing import Any, Protocol

@dataclass
class AIRequest:
    user_id: int
    messages: list[dict[str, str]]
    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 2000
    metadata: dict[str, Any] | None = None

@dataclass
class AIResponse:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    request_id: str | None = None

class AIProvider(Protocol):
    name: str
    async def chat(self, request: AIRequest) -> AIResponse: ...

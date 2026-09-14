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


class AIGateway:
    """Small provider registry used by the API and background health workflows."""

    def __init__(self):
        self.providers: dict[str, AIProvider] = {}
        self.default_provider = ""

    def register(self, provider: AIProvider, default: bool = False) -> None:
        self.providers[provider.name] = provider
        if default or not self.default_provider:
            self.default_provider = provider.name

    async def chat(self, request: AIRequest, provider: str | None = None) -> AIResponse:
        name = provider or self.default_provider
        if name not in self.providers:
            raise RuntimeError("No AI provider configured")
        return await self.providers[name].chat(request)


gateway = AIGateway()

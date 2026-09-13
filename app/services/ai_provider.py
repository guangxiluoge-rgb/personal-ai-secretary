import httpx
from app.core.config import settings
from app.services.ai_gateway import AIProvider, AIRequest, AIResponse

class OpenAICompatibleProvider(AIProvider):
    name = "openai_compatible"
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model

    async def chat(self, request: AIRequest) -> AIResponse:
        if not self.base_url or not self.api_key or not self.model:
            raise RuntimeError("AI provider is not configured")
        payload = {"model": request.model or self.model, "messages": request.messages, "temperature": request.temperature, "max_tokens": request.max_tokens}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        usage = data.get("usage") or {}
        choice = (data.get("choices") or [{}])[0]
        return AIResponse(text=((choice.get("message") or {}).get("content") or ""), provider=self.name, model=payload["model"], input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0), request_id=data.get("id"))

class AIGateway:
    def __init__(self):
        self.providers: dict[str, AIProvider] = {}
        self.default_provider = ""

    def register(self, provider: AIProvider, default: bool = False):
        self.providers[provider.name] = provider
        if default or not self.default_provider:
            self.default_provider = provider.name

    async def chat(self, request: AIRequest, provider: str | None = None) -> AIResponse:
        name = provider or self.default_provider
        if name not in self.providers:
            raise RuntimeError("No AI provider configured")
        return await self.providers[name].chat(request)

gateway = AIGateway()

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(RegisterIn):
    pass


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    layer: str = "temporary"
    memory_type: str = "fact"
    importance: float = Field(0.5, ge=0, le=1)
    confidence: float = Field(0.8, ge=0, le=1)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    model: str | None = None
    conversation_id: int | None = None
    conversation_kind: str = Field(default="chat", max_length=32)


class ChatOut(BaseModel):
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    conversation_id: int
    risk_alerts: list[dict] = Field(default_factory=list)

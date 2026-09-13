from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import get_current_user_id
from app.db import get_db
from app.models import AIUsage
from app.schemas import ChatIn, ChatOut
from app.services.ai_gateway import AIRequest, AIGateway
from app.services.ai_provider import OpenAICompatibleProvider
from app.services.memory_service import retrieve_context

router = APIRouter(prefix="/api/ai", tags=["ai"])
gateway = AIGateway()

async def _chat(data: ChatIn, user_id: int, db: Session):
    if not gateway.providers and settings.antfu_api_url and settings.antfu_api_key and settings.antfu_model:
        gateway.register(OpenAICompatibleProvider(settings.antfu_api_url, settings.antfu_api_key, settings.antfu_model), default=True)
    context = retrieve_context(db, user_id)
    system = "你是个人AI助理。保持连续性，但绝不虚构用户记忆。健康相关内容仅作健康管理与风险提示，不替代医生诊断。"
    if context:
        system += "\n用户相关记忆：\n- " + "\n- ".join(context)
    try:
        result = await gateway.chat(AIRequest(user_id=user_id, model=data.model, messages=[{"role":"system","content":system},{"role":"user","content":data.message}]))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    db.add(AIUsage(user_id=user_id, provider=result.provider, model=result.model, input_tokens=result.input_tokens, output_tokens=result.output_tokens, request_id=result.request_id))
    db.commit()
    return ChatOut(text=result.text, provider=result.provider, model=result.model, input_tokens=result.input_tokens, output_tokens=result.output_tokens)

@router.post("/chat", response_model=ChatOut)
async def chat(data: ChatIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return await _chat(data, user_id, db)

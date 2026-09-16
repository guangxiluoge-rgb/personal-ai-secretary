from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db import get_db
from app.models import AIUsage
from app.schemas import ChatIn, ChatOut
from app.services.ai_gateway import AIRequest, AIGateway
from app.services.ai_provider import OpenAICompatibleProvider
from app.services.life_os import add_message, auto_archive_message, create_conversation, get_conversation
from app.services.memory_service import retrieve_context
from app.services.runtime_config import load_runtime_config

router = APIRouter(prefix="/api/ai", tags=["ai"])
gateway = AIGateway()


async def _chat(data: ChatIn, user_id: int, db: Session):
    config = load_runtime_config(db)
    gateway.providers.clear()
    gateway.default_provider = ""
    if config.antfu_api_url and config.antfu_api_key and config.antfu_model:
        gateway.register(OpenAICompatibleProvider(config.antfu_api_url, config.antfu_api_key, config.antfu_model), default=True)

    conversation = get_conversation(db, user_id, data.conversation_id) if data.conversation_id else None
    if conversation is None:
        conversation = create_conversation(db, user_id, kind=data.conversation_kind)
    try:
        user_message = add_message(db, user_id, conversation.id, "user", data.message)
        risk_alerts = auto_archive_message(db, user_id, conversation, user_message)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    context = retrieve_context(db, user_id, limit=12, max_chars=6000)
    system = "你是个人AI助理。保持连续性，但绝不虚构用户记忆。健康相关内容仅作健康管理与风险提示，不替代医生诊断。"
    if context:
        system += "\n用户相关记忆（按重要性筛选，可能存在过期边界）：\n- " + "\n- ".join(context)
    try:
        result = await gateway.chat(AIRequest(user_id=user_id, model=data.model, messages=[{"role": "system", "content": system}, {"role": "user", "content": data.message}]))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    assistant_message = add_message(db, user_id, conversation.id, "assistant", result.text)
    auto_archive_message(db, user_id, conversation, assistant_message)
    db.add(AIUsage(user_id=user_id, provider=result.provider, model=result.model, input_tokens=result.input_tokens, output_tokens=result.output_tokens, request_id=result.request_id))
    db.commit()
    return ChatOut(text=result.text, provider=result.provider, model=result.model, input_tokens=result.input_tokens, output_tokens=result.output_tokens, conversation_id=conversation.id, risk_alerts=[{"id": a.id, "category": a.category, "severity": a.severity, "evidence": a.evidence, "advice": a.advice} for a in risk_alerts])


@router.post("/chat", response_model=ChatOut)
async def chat(data: ChatIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return await _chat(data, user_id, db)

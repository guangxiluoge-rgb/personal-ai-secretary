from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import ArchiveEntry, Conversation, ConversationMessage, MeetingNote, Person, RelationshipEvent, RiskAlert
from app.models.task import LifeTask
from app.services.memory_service import add_memory

RISK_RULES = [
    ("urgent_transfer", "high", ["马上转账", "立即转账", "立刻转账", "赶紧转", "现在转钱"]),
    ("guarantee_fee", "high", ["保证金", "解冻费", "手续费", "认证费", "押金"]),
    ("impersonation", "high", ["验证码", "登录码", "密码", "远程控制", "共享屏幕"]),
    ("investment_promise", "high", ["稳赚", "保本高收益", "高收益", "内部项目", "内幕消息"]),
    ("urgency_pressure", "medium", ["马上", "立刻", "今天必须", "最后机会", "不能告诉别人"]),
]


def create_conversation(db: Session, user_id: int, title: str = "新对话", kind: str = "chat") -> Conversation:
    row = Conversation(user_id=user_id, title=title[:200], kind=kind, status="active")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_conversation(db: Session, user_id: int, conversation_id: int) -> Conversation | None:
    return db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == user_id).first()


def add_message(db: Session, user_id: int, conversation_id: int, role: str, content: str) -> ConversationMessage:
    conversation = get_conversation(db, user_id, conversation_id)
    if conversation is None:
        raise ValueError("conversation not found")
    row = ConversationMessage(conversation_id=conversation.id, role=role, content=content)
    conversation.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _extract_people(text: str) -> list[str]:
    names: list[str] = []
    patterns = [r"联系人[:：]\s*([\u4e00-\u9fffA-Za-z0-9·_-]{2,20})", r"(?:和|跟|与)\s*([\u4e00-\u9fffA-Za-z]{2,8})(?:说|聊|谈|联系)"]
    for pattern in patterns:
        names.extend(re.findall(pattern, text))
    unique: list[str] = []
    for name in names:
        if name not in unique:
            unique.append(name)
    return unique[:5]


def _risk_matches(text: str) -> list[tuple[str, str, str]]:
    matches = []
    for category, severity, keywords in RISK_RULES:
        hit = next((kw for kw in keywords if kw in text), None)
        if hit:
            matches.append((category, severity, hit))
    return matches


def _risk_advice(category: str) -> str:
    advice = {
        "urgent_transfer": "先暂停付款，核实收款人身份、合同、账户和原始业务来源。不要因为催促而立即转账。",
        "guarantee_fee": "不要仅凭对方口头承诺支付保证金、解冻费或手续费；先核实合同、主体和官方联系方式。",
        "impersonation": "不要提供验证码、密码或远程控制权限。通过已知渠道独立联系本人或官方机构核实。",
        "investment_promise": "对高收益、保本或内部项目保持谨慎，不要先付款换取所谓资格或名额。",
        "urgency_pressure": "先停止继续操作，给自己留出核实时间，不要因为制造紧迫感而绕过正常流程。",
    }
    return advice[category]


def auto_archive_message(db: Session, user_id: int, conversation: Conversation, message: ConversationMessage) -> list[RiskAlert]:
    text = message.content.strip()
    alerts: list[RiskAlert] = []
    if not text:
        return alerts

    for name in _extract_people(text):
        person = db.query(Person).filter(Person.user_id == user_id, Person.name == name).first()
        if person is None:
            person = Person(user_id=user_id, name=name)
            db.add(person)
            db.flush()
        event = RelationshipEvent(user_id=user_id, person_id=person.id, event_type="interaction", summary=text[:1000])
        db.add(event)
        if conversation.title == "新对话":
            conversation.title = f"与{name}的对话"

    for category, severity, keyword in _risk_matches(text):
        advice = _risk_advice(category)
        alert = RiskAlert(user_id=user_id, conversation_id=conversation.id, category=category, severity=severity, evidence=f"命中关键词：{keyword}；原文：{text[:1200]}", advice=advice)
        db.add(alert)
        alerts.append(alert)

    if conversation.kind == "meeting" or any(k in text for k in ("会议", "开会", "会议纪要", "meeting")):
        summary = text[:2000]
        note = db.query(MeetingNote).filter(MeetingNote.conversation_id == conversation.id).order_by(MeetingNote.id.desc()).first()
        if note is None:
            note = MeetingNote(user_id=user_id, conversation_id=conversation.id, title=conversation.title or "会议记录", summary=summary)
            db.add(note)
        else:
            note.summary = (note.summary + "\n" + summary)[-6000:]

    archive = ArchiveEntry(
        user_id=user_id,
        entry_type="conversation_message",
        source_id=message.id,
        title=conversation.title,
        summary=text[:1000],
        content_json=json.dumps({"conversation_id": conversation.id, "role": message.role}, ensure_ascii=False),
    )
    db.add(archive)

    memory_text = text[:1500]
    if message.role == "user" and (len(text) >= 20 or alerts or _extract_people(text)):
        add_memory(db, user_id, memory_text, layer="episodic", memory_type="conversation_fact", importance=0.55, confidence=0.75)

    db.commit()
    for alert in alerts:
        db.refresh(alert)
    return alerts


def list_conversations(db: Session, user_id: int, limit: int = 50) -> list[Conversation]:
    limit = max(1, min(limit, 100))
    return db.query(Conversation).filter(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc()).limit(limit).all()


def list_messages(db: Session, user_id: int, conversation_id: int, limit: int = 200) -> list[ConversationMessage]:
    conversation = get_conversation(db, user_id, conversation_id)
    if conversation is None:
        return []
    return db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conversation_id).order_by(ConversationMessage.created_at.asc()).limit(max(1, min(limit, 500))).all()


def build_meeting_note(db: Session, user_id: int, conversation_id: int) -> MeetingNote | None:
    conversation = get_conversation(db, user_id, conversation_id)
    if conversation is None:
        return None
    messages = list_messages(db, user_id, conversation_id, 500)
    if not messages:
        return None
    users = [m.content.strip() for m in messages if m.role == "user" and m.content.strip()]
    text = "\n".join(users)[-8000:]
    decisions = [line for line in text.splitlines() if any(k in line for k in ("决定", "确定", "通过"))][:10]
    actions = [line for line in text.splitlines() if any(k in line for k in ("待办", "TODO", "负责", "截止"))][:10]
    risks = [f"{alert.category}: {alert.evidence}" for alert in db.query(RiskAlert).filter(RiskAlert.user_id == user_id, RiskAlert.conversation_id == conversation_id).all()][:10]
    note = db.query(MeetingNote).filter(MeetingNote.conversation_id == conversation_id).order_by(MeetingNote.id.desc()).first()
    if note is None:
        note = MeetingNote(user_id=user_id, conversation_id=conversation_id, title=conversation.title or "会议记录")
        db.add(note)
    note.summary = text[-3000:]
    note.decisions_json = json.dumps(decisions, ensure_ascii=False)
    note.actions_json = json.dumps(actions, ensure_ascii=False)
    note.risks_json = json.dumps(risks, ensure_ascii=False)
    conversation.kind = "meeting"

    existing_titles = {row.title for row in db.query(LifeTask).filter(LifeTask.user_id == user_id, LifeTask.conversation_id == conversation_id, LifeTask.status == "open").all()}
    for action in actions:
        title = action.strip()[:240]
        if title and title not in existing_titles:
            db.add(LifeTask(user_id=user_id, conversation_id=conversation_id, title=title, task_type="meeting_action", priority="high" if "截止" in title else "normal", source="meeting_note", notes="从会议纪要自动生成；请补充明确负责人和截止时间。"))

    db.commit()
    db.refresh(note)
    return note

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db import get_db
from app.models import ArchiveEntry, Person, RiskAlert
from app.services.life_os import (
    add_message,
    build_meeting_note,
    create_conversation,
    get_conversation,
    list_conversations,
    list_messages,
)

router = APIRouter(prefix="/api/life-os", tags=["life-os"])


class ConversationIn(BaseModel):
    title: str = Field(default="新对话", max_length=200)
    kind: str = Field(default="chat", max_length=32)


class MessageIn(BaseModel):
    role: str = Field(min_length=1, max_length=16)
    content: str = Field(min_length=1, max_length=20000)


@router.post("/conversations")
def conversation_create(data: ConversationIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    row = create_conversation(db, user_id, data.title, data.kind)
    return {"id": row.id, "title": row.title, "kind": row.kind, "status": row.status}


@router.get("/conversations")
def conversation_list(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = list_conversations(db, user_id)
    return [{"id": r.id, "title": r.title, "kind": r.kind, "status": r.status, "updated_at": r.updated_at} for r in rows]


@router.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    row = get_conversation(db, user_id, conversation_id)
    if row is None:
        raise HTTPException(404, "conversation not found")
    messages = list_messages(db, user_id, conversation_id)
    return {
        "id": row.id,
        "title": row.title,
        "kind": row.kind,
        "status": row.status,
        "messages": [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at} for m in messages],
    }


@router.post("/conversations/{conversation_id}/messages")
def message_add(conversation_id: int, data: MessageIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    try:
        row = add_message(db, user_id, conversation_id, data.role, data.content)
        from app.services.life_os import auto_archive_message
        conversation = get_conversation(db, user_id, conversation_id)
        alerts = auto_archive_message(db, user_id, conversation, row)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"message_id": row.id, "risk_alerts": [{"id": a.id, "category": a.category, "severity": a.severity, "evidence": a.evidence, "advice": a.advice} for a in alerts]}


@router.post("/conversations/{conversation_id}/meeting-note")
def meeting_note(conversation_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    note = build_meeting_note(db, user_id, conversation_id)
    if note is None:
        raise HTTPException(404, "conversation not found or has no messages")
    return {
        "id": note.id,
        "conversation_id": note.conversation_id,
        "title": note.title,
        "summary": note.summary,
        "decisions": json.loads(note.decisions_json),
        "actions": json.loads(note.actions_json),
        "risks": json.loads(note.risks_json),
    }


@router.get("/people")
def people(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = db.query(Person).filter(Person.user_id == user_id).order_by(Person.updated_at.desc()).limit(200).all()
    return [{"id": p.id, "name": p.name, "relationship_type": p.relationship_type, "notes": p.notes, "importance": p.importance, "updated_at": p.updated_at} for p in rows]


@router.get("/risks")
def risks(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = db.query(RiskAlert).filter(RiskAlert.user_id == user_id, RiskAlert.status == "open").order_by(RiskAlert.created_at.desc()).limit(100).all()
    return [{"id": r.id, "category": r.category, "severity": r.severity, "evidence": r.evidence, "advice": r.advice, "created_at": r.created_at} for r in rows]


@router.get("/archive")
def archive(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = db.query(ArchiveEntry).filter(ArchiveEntry.user_id == user_id).order_by(ArchiveEntry.created_at.desc()).limit(200).all()
    return [{"id": r.id, "entry_type": r.entry_type, "source_id": r.source_id, "title": r.title, "summary": r.summary, "created_at": r.created_at} for r in rows]

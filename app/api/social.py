from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db import get_db
from app.models import Person, RelationshipEvent
from app.models.social_circle import SocialCircle, SocialCircleMember
from app.models.task import LifeTask
from app.services.life_os import add_message, auto_archive_message, create_conversation
from app.services.social_circle import add_member, circle_snapshot, create_circle, create_event, create_topic, relationship_reminders, search_circle_people
from app.services.task_service import complete_task, create_task, list_open_tasks, task_payload

router = APIRouter(prefix="/api/social", tags=["social-circle"])


class CircleIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    visibility: str = Field(default="private", max_length=24)


class MemberIn(BaseModel):
    person_id: int
    role: str = Field(default="member", max_length=32)
    tags: str = Field(default="", max_length=2000)


class TopicIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=5000)
    tags: str = Field(default="", max_length=2000)


class EventIn(BaseModel):
    event_type: str = Field(min_length=1, max_length=48)
    summary: str = Field(min_length=1, max_length=8000)
    person_id: int | None = None
    topic_id: int | None = None
    source: str = Field(default="manual", max_length=48)
    occurred_at: datetime | None = None


class ReminderIn(BaseModel):
    event_type: str = Field(default="follow_up", max_length=64)
    summary: str = Field(min_length=1, max_length=2000)
    due_at: datetime


class MessageIn(BaseModel):
    source: str = Field(default="import", max_length=48)
    sender_name: str = Field(default="", max_length=120)
    content: str = Field(min_length=1, max_length=20000)
    person_id: int | None = None


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    task_type: str = Field(default="follow_up", max_length=48)
    priority: str = Field(default="normal", max_length=16)
    due_at: datetime | None = None
    notes: str = Field(default="", max_length=6000)
    person_id: int | None = None
    conversation_id: int | None = None


@router.post("/circles")
def circle_create(data: CircleIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    row = create_circle(db, user_id, data.name, data.description, data.visibility)
    return {"id": row.id, "name": row.name, "description": row.description, "visibility": row.visibility, "status": row.status}


@router.get("/circles")
def circle_list(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = db.query(SocialCircle).filter(SocialCircle.user_id == user_id, SocialCircle.status == "active").order_by(SocialCircle.updated_at.desc()).limit(100).all()
    counts = {}
    for circle in rows:
        counts[circle.id] = db.query(SocialCircleMember).filter(SocialCircleMember.circle_id == circle.id, SocialCircleMember.status == "active").count()
    return [{"id": r.id, "name": r.name, "description": r.description, "visibility": r.visibility, "member_count": counts[r.id], "updated_at": r.updated_at} for r in rows]


@router.get("/circles/{circle_id}")
def circle_detail(circle_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    snapshot = circle_snapshot(db, user_id, circle_id)
    if snapshot is None:
        raise HTTPException(404, "circle not found")
    return snapshot


@router.post("/circles/{circle_id}/members")
def circle_member_add(circle_id: int, data: MemberIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    try:
        row = add_member(db, user_id, circle_id, data.person_id, data.role, data.tags)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"id": row.id, "circle_id": row.circle_id, "person_id": row.person_id, "role": row.role, "tags": row.tags, "status": row.status}


@router.post("/circles/{circle_id}/topics")
def circle_topic_create(circle_id: int, data: TopicIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    try:
        row = create_topic(db, user_id, circle_id, data.title, data.summary, data.tags)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"id": row.id, "circle_id": row.circle_id, "title": row.title, "summary": row.summary, "tags": row.tags}


@router.post("/circles/{circle_id}/events")
def circle_event_create(circle_id: int, data: EventIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    try:
        row = create_event(db, user_id, circle_id, data.event_type, data.summary, data.person_id, data.topic_id, data.source, data.occurred_at)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"id": row.id, "circle_id": row.circle_id, "person_id": row.person_id, "topic_id": row.topic_id, "event_type": row.event_type, "summary": row.summary, "source": row.source, "occurred_at": row.occurred_at}


@router.get("/people/search")
def people_search(q: str = "", db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    if not q.strip():
        rows = db.query(Person).filter(Person.user_id == user_id).order_by(Person.updated_at.desc()).limit(100).all()
    else:
        rows = search_circle_people(db, user_id, q)
    return [{"id": p.id, "name": p.name, "relationship_type": p.relationship_type, "notes": p.notes, "importance": p.importance} for p in rows]


@router.post("/people/{person_id}/reminders")
def reminder_create(person_id: int, data: ReminderIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    person = db.query(Person).filter(Person.id == person_id, Person.user_id == user_id).first()
    if person is None:
        raise HTTPException(404, "person not found")
    row = RelationshipEvent(user_id=user_id, person_id=person_id, event_type=data.event_type, summary=data.summary, due_at=data.due_at)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "person_id": row.person_id, "person_name": person.name, "event_type": row.event_type, "summary": row.summary, "due_at": row.due_at}


@router.get("/reminders")
def reminders(horizon_days: int = 30, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return relationship_reminders(db, user_id, horizon_days)


@router.post("/tasks")
def task_create(data: TaskIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    try:
        row = create_task(db, user_id, data.title, data.task_type, data.priority, data.due_at, "manual", data.notes, data.person_id, data.conversation_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return task_payload(db, row)


@router.get("/tasks")
def task_list(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return [task_payload(db, row) for row in list_open_tasks(db, user_id)]


@router.post("/tasks/{task_id}/complete")
def task_complete(task_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    row = complete_task(db, user_id, task_id)
    if row is None:
        raise HTTPException(404, "task not found")
    return task_payload(db, row)


@router.post("/messages/ingest")
def message_ingest(data: MessageIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    title = f"{data.source}: {data.sender_name}" if data.sender_name else data.source
    conversation = create_conversation(db, user_id, title[:200], "external")
    row = add_message(db, user_id, conversation.id, "user", data.content)
    alerts = auto_archive_message(db, user_id, conversation, row)
    if data.person_id is not None:
        person = db.query(Person).filter(Person.id == data.person_id, Person.user_id == user_id).first()
        if person is None:
            raise HTTPException(404, "person not found")
        db.add(RelationshipEvent(user_id=user_id, person_id=person.id, event_type="external_message", summary=f"[{data.source}] {data.content[:1800]}"))
        db.commit()
    return {
        "conversation_id": conversation.id,
        "message_id": row.id,
        "source": data.source,
        "risk_alerts": [{"id": a.id, "category": a.category, "severity": a.severity, "evidence": a.evidence, "advice": a.advice} for a in alerts],
    }


@router.get("/briefing")
def briefing(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    from app.models import MeetingNote, RiskAlert

    reminders_data = relationship_reminders(db, user_id, 30)
    tasks = [task_payload(db, row) for row in list_open_tasks(db, user_id, 50)]
    risks = db.query(RiskAlert).filter(RiskAlert.user_id == user_id, RiskAlert.status == "open").order_by(RiskAlert.created_at.desc()).limit(20).all()
    meetings = db.query(MeetingNote).filter(MeetingNote.user_id == user_id).order_by(MeetingNote.created_at.desc()).limit(20).all()
    circles = db.query(SocialCircle).filter(SocialCircle.user_id == user_id, SocialCircle.status == "active").order_by(SocialCircle.updated_at.desc()).limit(20).all()
    return {
        "generated_at": datetime.utcnow(),
        "relationship_reminders": reminders_data,
        "tasks": tasks,
        "risk_alerts": [{"id": r.id, "category": r.category, "severity": r.severity, "advice": r.advice} for r in risks],
        "recent_meetings": [{"id": m.id, "title": m.title, "summary": m.summary[:500]} for m in meetings],
        "social_circles": [{"id": c.id, "name": c.name, "description": c.description} for c in circles],
    }

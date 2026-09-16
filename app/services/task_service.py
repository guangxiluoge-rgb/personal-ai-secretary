from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Person
from app.models.task import LifeTask


def create_task(
    db: Session,
    user_id: int,
    title: str,
    task_type: str = "follow_up",
    priority: str = "normal",
    due_at: datetime | None = None,
    source: str = "manual",
    notes: str = "",
    person_id: int | None = None,
    conversation_id: int | None = None,
) -> LifeTask:
    if person_id is not None:
        person = db.query(Person).filter(Person.id == person_id, Person.user_id == user_id).first()
        if person is None:
            raise ValueError("person not found")
    row = LifeTask(
        user_id=user_id,
        person_id=person_id,
        conversation_id=conversation_id,
        title=title[:240],
        task_type=task_type[:48],
        priority=priority[:16],
        due_at=due_at,
        source=source[:48],
        notes=notes[:6000],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_open_tasks(db: Session, user_id: int, limit: int = 100) -> list[LifeTask]:
    return (
        db.query(LifeTask)
        .filter(LifeTask.user_id == user_id, LifeTask.status == "open")
        .order_by(LifeTask.due_at.is_(None), LifeTask.due_at.asc(), LifeTask.priority.desc(), LifeTask.created_at.desc())
        .limit(max(1, min(limit, 300)))
        .all()
    )


def complete_task(db: Session, user_id: int, task_id: int) -> LifeTask | None:
    row = db.query(LifeTask).filter(LifeTask.id == task_id, LifeTask.user_id == user_id).first()
    if row is None:
        return None
    row.status = "completed"
    row.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def task_payload(db: Session, row: LifeTask) -> dict:
    person = db.query(Person).filter(Person.id == row.person_id).first() if row.person_id else None
    now = datetime.utcnow()
    return {
        "id": row.id,
        "title": row.title,
        "task_type": row.task_type,
        "priority": row.priority,
        "status": row.status,
        "due_at": row.due_at,
        "overdue": bool(row.due_at and row.status == "open" and row.due_at < now),
        "source": row.source,
        "notes": row.notes,
        "person_id": row.person_id,
        "person_name": person.name if person else None,
        "conversation_id": row.conversation_id,
    }

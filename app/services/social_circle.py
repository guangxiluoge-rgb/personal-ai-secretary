from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Person, RelationshipEvent
from app.models.social_circle import SocialCircle, SocialCircleEvent, SocialCircleMember, SocialCircleTopic


def get_circle(db: Session, user_id: int, circle_id: int) -> SocialCircle | None:
    return db.query(SocialCircle).filter(SocialCircle.id == circle_id, SocialCircle.user_id == user_id).first()


def create_circle(db: Session, user_id: int, name: str, description: str = "", visibility: str = "private") -> SocialCircle:
    row = SocialCircle(user_id=user_id, name=name[:160], description=description[:5000], visibility=visibility[:24])
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_member(db: Session, user_id: int, circle_id: int, person_id: int, role: str = "member", tags: str = "") -> SocialCircleMember:
    circle = get_circle(db, user_id, circle_id)
    person = db.query(Person).filter(Person.id == person_id, Person.user_id == user_id).first()
    if circle is None or person is None:
        raise ValueError("circle or person not found")
    row = db.query(SocialCircleMember).filter(SocialCircleMember.circle_id == circle_id, SocialCircleMember.person_id == person_id).first()
    if row is None:
        row = SocialCircleMember(circle_id=circle_id, person_id=person_id, role=role[:32], tags=tags[:2000])
        db.add(row)
    else:
        row.role = role[:32]
        row.tags = tags[:2000]
        row.status = "active"
    db.commit()
    db.refresh(row)
    return row


def create_topic(db: Session, user_id: int, circle_id: int, title: str, summary: str = "", tags: str = "") -> SocialCircleTopic:
    circle = get_circle(db, user_id, circle_id)
    if circle is None:
        raise ValueError("circle not found")
    row = SocialCircleTopic(circle_id=circle_id, title=title[:200], summary=summary[:5000], tags=tags[:2000])
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_event(
    db: Session,
    user_id: int,
    circle_id: int,
    event_type: str,
    summary: str,
    person_id: int | None = None,
    topic_id: int | None = None,
    source: str = "manual",
    occurred_at: datetime | None = None,
) -> SocialCircleEvent:
    circle = get_circle(db, user_id, circle_id)
    if circle is None:
        raise ValueError("circle not found")
    person = None
    if person_id is not None:
        person = db.query(Person).filter(Person.id == person_id, Person.user_id == user_id).first()
        if person is None:
            raise ValueError("person not found")
    topic = None
    if topic_id is not None:
        topic = db.query(SocialCircleTopic).filter(SocialCircleTopic.id == topic_id, SocialCircleTopic.circle_id == circle_id).first()
        if topic is None:
            raise ValueError("topic not found")
    row = SocialCircleEvent(
        circle_id=circle_id,
        person_id=person_id,
        topic_id=topic_id,
        event_type=event_type[:48],
        summary=summary[:8000],
        source=source[:48],
        occurred_at=occurred_at or datetime.utcnow(),
    )
    db.add(row)
    if topic is not None:
        topic.last_interaction_at = row.occurred_at
    if person is not None:
        db.add(RelationshipEvent(user_id=user_id, person_id=person.id, event_type=f"social:{event_type[:48]}", summary=summary[:2000]))
    db.commit()
    db.refresh(row)
    return row


def circle_snapshot(db: Session, user_id: int, circle_id: int) -> dict | None:
    circle = get_circle(db, user_id, circle_id)
    if circle is None:
        return None
    members = (
        db.query(SocialCircleMember, Person)
        .join(Person, Person.id == SocialCircleMember.person_id)
        .filter(SocialCircleMember.circle_id == circle_id, Person.user_id == user_id, SocialCircleMember.status == "active")
        .order_by(Person.updated_at.desc())
        .limit(500)
        .all()
    )
    topics = db.query(SocialCircleTopic).filter(SocialCircleTopic.circle_id == circle_id, SocialCircleTopic.status == "active").order_by(SocialCircleTopic.updated_at.desc()).limit(200).all()
    events = db.query(SocialCircleEvent).filter(SocialCircleEvent.circle_id == circle_id).order_by(SocialCircleEvent.occurred_at.desc()).limit(200).all()
    return {
        "id": circle.id,
        "name": circle.name,
        "description": circle.description,
        "visibility": circle.visibility,
        "status": circle.status,
        "members": [{"id": m.id, "person_id": p.id, "name": p.name, "role": m.role, "tags": m.tags} for m, p in members],
        "topics": [{"id": t.id, "title": t.title, "summary": t.summary, "tags": t.tags, "last_interaction_at": t.last_interaction_at} for t in topics],
        "events": [{"id": e.id, "person_id": e.person_id, "topic_id": e.topic_id, "event_type": e.event_type, "summary": e.summary, "source": e.source, "occurred_at": e.occurred_at} for e in events],
    }


def relationship_reminders(db: Session, user_id: int, horizon_days: int = 30) -> list[dict]:
    now = datetime.utcnow()
    horizon = now + timedelta(days=max(1, min(horizon_days, 365)))
    rows = (
        db.query(RelationshipEvent, Person)
        .join(Person, Person.id == RelationshipEvent.person_id)
        .filter(
            RelationshipEvent.user_id == user_id,
            Person.user_id == user_id,
            RelationshipEvent.due_at.isnot(None),
            RelationshipEvent.due_at <= horizon,
            RelationshipEvent.due_at >= now - timedelta(days=365),
        )
        .order_by(RelationshipEvent.due_at.asc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": event.id,
            "person_id": person.id,
            "person_name": person.name,
            "event_type": event.event_type,
            "summary": event.summary,
            "due_at": event.due_at,
            "overdue": bool(event.due_at and event.due_at < now),
        }
        for event, person in rows
    ]


def search_circle_people(db: Session, user_id: int, query: str, limit: int = 50) -> list[Person]:
    q = f"%{query.strip()}%"
    return db.query(Person).filter(Person.user_id == user_id, or_(Person.name.ilike(q), Person.relationship_type.ilike(q), Person.notes.ilike(q))).order_by(Person.updated_at.desc()).limit(max(1, min(limit, 100))).all()

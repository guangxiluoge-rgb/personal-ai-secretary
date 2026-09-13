import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Memory

LAYER_TTL_DAYS = {"temporary": 1, "working": 7, "episodic": 90, "semantic": None, "profile": None}
LAYER_WEIGHT = {"profile": 1.35, "semantic": 1.2, "episodic": 1.05, "working": 1.0, "temporary": 0.85}


def _normalize(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip())


def add_memory(db: Session, user_id: int, content: str, layer: str = "temporary", memory_type: str = "fact", importance: float = .5, confidence: float = .8):
    content = _normalize(content)
    if not content:
        raise ValueError("memory content cannot be empty")
    if layer not in LAYER_TTL_DAYS:
        raise ValueError("invalid memory layer")
    existing = db.query(Memory).filter(Memory.user_id == user_id, Memory.content == content, Memory.layer == layer).first()
    if existing:
        existing.importance = max(existing.importance, importance)
        existing.confidence = max(existing.confidence, confidence)
        existing.updated_at = datetime.utcnow()
        ttl = LAYER_TTL_DAYS[layer]
        if ttl:
            existing.expires_at = datetime.utcnow() + timedelta(days=ttl)
        db.commit()
        db.refresh(existing)
        return existing
    ttl = LAYER_TTL_DAYS[layer]
    expires_at = datetime.utcnow() + timedelta(days=ttl) if ttl else None
    m = Memory(user_id=user_id, content=content, layer=layer, memory_type=memory_type, importance=importance, confidence=confidence, expires_at=expires_at)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def retrieve_context(db: Session, user_id: int, limit: int = 12, max_chars: int = 6000) -> list[str]:
    now = datetime.utcnow()
    rows = db.query(Memory).filter(Memory.user_id == user_id).filter((Memory.expires_at.is_(None)) | (Memory.expires_at > now)).all()
    ranked = sorted(rows, key=lambda r: (r.importance * r.confidence * LAYER_WEIGHT.get(r.layer, 1.0), r.updated_at), reverse=True)
    selected: list[str] = []
    used = 0
    for row in ranked:
        if len(selected) >= limit:
            break
        text = row.content.strip()
        cost = len(text)
        if used + cost > max_chars and selected:
            continue
        selected.append(text)
        used += cost
        if used >= max_chars:
            break
    return selected


def maintain(db: Session):
    db.query(Memory).filter(Memory.expires_at.is_not(None), Memory.expires_at < datetime.utcnow()).delete(synchronize_session=False)
    db.commit()

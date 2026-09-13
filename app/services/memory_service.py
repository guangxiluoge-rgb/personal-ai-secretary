from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Memory

LAYER_TTL_DAYS = {"temporary": 1, "working": 7, "episodic": 90, "semantic": None, "profile": None}

def add_memory(db: Session, user_id: int, content: str, layer: str = "temporary", memory_type: str = "fact", importance: float = .5, confidence: float = .8):
    content = content.strip()
    if layer not in LAYER_TTL_DAYS:
        raise ValueError("invalid memory layer")
    # Exact duplicates are merged instead of consuming more context/token budget.
    existing = db.query(Memory).filter(Memory.user_id == user_id, Memory.content == content, Memory.layer == layer).first()
    if existing:
        existing.importance = max(existing.importance, importance)
        existing.confidence = max(existing.confidence, confidence)
        existing.updated_at = datetime.utcnow()
        db.commit(); db.refresh(existing)
        return existing
    ttl = LAYER_TTL_DAYS[layer]
    expires_at = datetime.utcnow() + timedelta(days=ttl) if ttl else None
    m = Memory(user_id=user_id, content=content, layer=layer, memory_type=memory_type, importance=importance, confidence=confidence, expires_at=expires_at)
    db.add(m); db.commit(); db.refresh(m)
    return m

def retrieve_context(db: Session, user_id: int, limit: int = 12) -> list[str]:
    now = datetime.utcnow()
    rows = db.query(Memory).filter(Memory.user_id == user_id).filter((Memory.expires_at.is_(None)) | (Memory.expires_at > now)).order_by((Memory.importance * Memory.confidence).desc(), Memory.updated_at.desc()).limit(limit).all()
    return [r.content for r in rows]

def maintain(db: Session):
    db.query(Memory).filter(Memory.expires_at.is_not(None), Memory.expires_at < datetime.utcnow()).delete(synchronize_session=False)
    db.commit()

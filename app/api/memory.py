from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import get_current_user_id
from app.db import get_db
from app.models import Memory
from app.schemas import MemoryIn
from app.services.memory_service import add_memory, retrieve_context

router = APIRouter(prefix="/api/memory", tags=["memory"])

@router.post("")
def create(data: MemoryIn, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    try:
        m = add_memory(db, user_id, **data.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": m.id, "layer": m.layer, "content": m.content}

@router.get("")
def list_memories(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = db.query(Memory).filter(Memory.user_id == user_id).order_by(Memory.updated_at.desc()).limit(100).all()
    return [{"id": r.id, "layer": r.layer, "type": r.memory_type, "content": r.content, "importance": r.importance, "confidence": r.confidence} for r in rows]

@router.get("/context")
def context(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return {"items": retrieve_context(db, user_id)}

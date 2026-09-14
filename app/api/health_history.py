import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db import get_db
from app.services.health_history import four_week_metrics, get_history_report, list_history

router = APIRouter(prefix="/api/health/history", tags=["health-history"])


@router.get("")
def history(limit: int = Query(12, ge=1, le=52), db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rows = list_history(db, user_id, limit)
    return {
        "reports": [
            {
                "week_start": row.week_start.date().isoformat(),
                "updated_at": row.updated_at,
                "source_context_hash": row.source_context_hash,
            }
            for row in rows
        ]
    }


@router.get("/report")
def history_report(week_start: str, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    try:
        row = get_history_report(db, user_id, week_start)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not row:
        raise HTTPException(404, "weekly report not found")
    return {
        "status": row.status,
        "week_start": row.week_start,
        "updated_at": row.updated_at,
        "report": json.loads(row.report_json),
    }


@router.get("/four-weeks")
def history_four_weeks(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return four_week_metrics(db, user_id)

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db import get_db
from app.services.health_long_term import monthly_profile, quarterly_profile

router = APIRouter(prefix="/api/health/long-term", tags=["health-long-term"])


@router.get("/monthly")
def monthly(
    months: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return monthly_profile(db, user_id, months=months)


@router.get("/quarterly")
def quarterly(
    quarters: int = Query(4, ge=1, le=8),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return quarterly_profile(db, user_id, quarters=quarters)

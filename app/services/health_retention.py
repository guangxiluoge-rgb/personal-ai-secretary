from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import HealthAnalysisJob


def cleanup_expired_health_images(db: Session, retention_days: int) -> int:
    if retention_days < 1:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    removed = 0
    jobs = (
        db.query(HealthAnalysisJob)
        .filter(
            HealthAnalysisJob.status == "completed",
            HealthAnalysisJob.completed_at.is_not(None),
        )
        .yield_per(100)
    )
    for job in jobs:
        completed_at = job.completed_at
        if completed_at is None:
            continue
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)
        if completed_at > cutoff:
            continue
        path = Path(job.file_path)
        try:
            path.unlink(missing_ok=True)
            removed += 1
        except OSError:
            continue
    return removed

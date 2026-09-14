"""Generate the current weekly health report for all active users.

Run this from a scheduled job once a week (for example Monday early morning).
The report is idempotent for unchanged weekly source data.
"""

import asyncio

from app.db import SessionLocal
from app.models import User
from app.services.weekly_health_report import generate_weekly_report


async def main() -> None:
    db = SessionLocal()
    try:
        user_ids = [row.id for row in db.query(User.id).filter(User.is_active.is_(True)).all()]
        for user_id in user_ids:
            await generate_weekly_report(db, user_id, force=False)
            db.expire_all()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

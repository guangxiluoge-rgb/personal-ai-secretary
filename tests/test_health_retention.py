from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.health_retention import cleanup_expired_health_images


def test_retention_cleanup_removes_old_completed_files(tmp_path, monkeypatch):
    old_path = tmp_path / "old.jpg"
    old_path.write_bytes(b"x")
    recent_path = tmp_path / "recent.jpg"
    recent_path.write_bytes(b"x")

    old_job = SimpleNamespace(
        file_path=str(old_path),
        status="completed",
        completed_at=datetime.now(timezone.utc) - timedelta(days=31),
    )
    recent_job = SimpleNamespace(
        file_path=str(recent_path),
        status="completed",
        completed_at=datetime.now(timezone.utc) - timedelta(days=2),
    )

    query = MagicMock()
    query.filter.return_value.yield_per.return_value = [old_job, recent_job]
    db = MagicMock()
    db.query.return_value = query

    removed = cleanup_expired_health_images(db, 30)

    assert removed == 1
    assert not old_path.exists()
    assert recent_path.exists()


def test_retention_cleanup_ignores_non_completed_jobs():
    job = SimpleNamespace(
        file_path="/tmp/should-not-delete.jpg",
        status="failed",
        completed_at=datetime.now(timezone.utc) - timedelta(days=90),
    )
    query = MagicMock()
    query.filter.return_value.yield_per.return_value = [job]
    db = MagicMock()
    db.query.return_value = query

    assert cleanup_expired_health_images(db, 30) == 1

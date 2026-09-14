from pathlib import Path

from sqlalchemy.orm import Session

from app.models import HealthAlert, HealthRecord

RISK_ORDER = {"normal": 0, "watch": 1, "urgent": 2}
IMAGE_SIGNATURES = {
    "image/jpeg": ((b"\xff\xd8\xff",),),
    "image/png": ((b"\x89PNG\r\n\x1a\n",),),
    "image/webp": ((b"RIFF", b"WEBP"),),
}


def save_record(
    db: Session,
    user_id: int,
    source: str,
    image_type: str,
    summary: str,
    risk_level: str = "normal",
):
    if risk_level not in RISK_ORDER:
        risk_level = "watch"
    record = HealthRecord(
        user_id=user_id,
        source=source,
        image_type=image_type,
        summary=summary,
        risk_level=risk_level,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    if risk_level == "urgent":
        alert = HealthAlert(
            user_id=user_id,
            record_id=record.id,
            severity="urgent",
            message="健康数据触发高风险阈值，请尽快进行人工/专业复核。",
        )
        db.add(alert)
        db.commit()
    return record


def validate_upload(path: Path, max_bytes: int):
    if not path.exists() or path.stat().st_size > max_bytes:
        raise ValueError("file missing or exceeds configured size")


def validate_image_bytes(raw: bytes, content_type: str) -> None:
    """Reject payloads whose bytes do not match the declared supported image type."""
    if content_type == "image/jpeg":
        valid = raw.startswith(b"\xff\xd8\xff")
    elif content_type == "image/png":
        valid = raw.startswith(b"\x89PNG\r\n\x1a\n")
    elif content_type == "image/webp":
        valid = len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
    else:
        valid = False
    if not valid:
        raise ValueError("uploaded bytes do not match the declared image type")

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Entitlement


def grant(
    db: Session,
    user_id: int,
    feature: str,
    source: str = "system",
    expires_at=None,
):
    row = (
        db.query(Entitlement)
        .filter(Entitlement.user_id == user_id, Entitlement.feature == feature)
        .first()
    )
    if not row:
        row = Entitlement(
            user_id=user_id,
            feature=feature,
            status="active",
            source=source,
            expires_at=expires_at,
        )
        db.add(row)
    else:
        row.status = "active"
        row.source = source
        row.expires_at = expires_at
    db.commit()
    db.refresh(row)
    return row


def extend(
    db: Session,
    user_id: int,
    feature: str,
    duration: timedelta,
    source: str = "system",
):
    now = datetime.utcnow()
    row = (
        db.query(Entitlement)
        .filter(Entitlement.user_id == user_id, Entitlement.feature == feature)
        .first()
    )
    base = row.expires_at if row and row.expires_at and row.expires_at > now else now
    return grant(db, user_id, feature, source=source, expires_at=base + duration)


def revoke(db: Session, user_id: int, feature: str):
    row = (
        db.query(Entitlement)
        .filter(Entitlement.user_id == user_id, Entitlement.feature == feature)
        .first()
    )
    if row:
        row.status = "revoked"
        db.commit()
    return row


def has_feature(db: Session, user_id: int, feature: str) -> bool:
    row = (
        db.query(Entitlement)
        .filter(
            Entitlement.user_id == user_id,
            Entitlement.feature == feature,
            Entitlement.status == "active",
        )
        .first()
    )
    return bool(row and (row.expires_at is None or row.expires_at > datetime.utcnow()))

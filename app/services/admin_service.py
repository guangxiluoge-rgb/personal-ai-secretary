from sqlalchemy.orm import Session
from app.models.admin import SystemSetting

EDITABLE_KEYS = {
    "antfu_api_url": False,
    "antfu_api_key": True,
    "antfu_model": False,
    "stripe_secret_key": True,
    "stripe_webhook_secret": True,
    "stripe_price_pro_monthly": False,
    "stripe_price_health_pro_monthly": False,
    "stripe_price_premium_monthly": False,
    "product_pro_monthly_price_minor": False,
    "product_health_pro_monthly_price_minor": False,
    "product_premium_monthly_price_minor": False,
    "cors_origins": False,
}

def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return row.value if row else default

def set_setting(db: Session, key: str, value: str) -> SystemSetting:
    if key not in EDITABLE_KEYS:
        raise ValueError("setting is not editable")
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        row = SystemSetting(key=key, value=value, is_secret=EDITABLE_KEYS[key])
        db.add(row)
    else:
        row.value = value
    db.commit()
    db.refresh(row)
    return row

def list_settings(db: Session):
    rows = db.query(SystemSetting).filter(SystemSetting.key.in_(EDITABLE_KEYS.keys())).order_by(SystemSetting.key).all()
    existing = {r.key: r for r in rows}
    return [{"key": key, "value": ("********" if EDITABLE_KEYS[key] and key in existing and existing[key].value else ""), "is_secret": EDITABLE_KEYS[key]} for key in EDITABLE_KEYS]

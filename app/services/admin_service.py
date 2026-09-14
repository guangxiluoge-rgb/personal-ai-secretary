from sqlalchemy.orm import Session

from app.core.secret_store import decrypt_secret, encrypt_secret
from app.models.admin import SystemSetting


EDITABLE_KEYS = {
    "ai_api_url": False,
    "ai_api_key": True,
    "ai_model": False,
    "gemini_api_key": True,
    "gemini_model": False,
    "stripe_secret_key": True,
    "stripe_webhook_secret": True,
    "stripe_price_pro_monthly": False,
    "stripe_price_health_pro_monthly": False,
    "stripe_price_premium_monthly": False,
    "stripe_success_url": False,
    "stripe_cancel_url": False,
    "product_pro_monthly_price_minor": False,
    "product_health_pro_monthly_price_minor": False,
    "product_premium_monthly_price_minor": False,
    "wechat_enabled": False,
    "wechat_app_id": False,
    "wechat_mch_id": False,
    "wechat_api_v3_key": True,
    "wechat_serial_no": False,
    "wechat_private_key": True,
    "wechat_platform_public_key": True,
    "wechat_notify_url": False,
    "payment_cny_pro_monthly_price_minor": False,
    "payment_cny_health_pro_monthly_price_minor": False,
    "payment_cny_premium_monthly_price_minor": False,
    "alipay_enabled": False,
    "alipay_app_id": False,
    "alipay_private_key": True,
    "alipay_public_key": True,
    "alipay_notify_url": False,
    "alipay_return_url": False,
    "alipay_gateway_url": False,
    "cors_origins": False,
    "health_image_retention_days": False,
}


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        return default
    return decrypt_secret(row.value) if EDITABLE_KEYS.get(key, row.is_secret) else row.value


def set_setting(db: Session, key: str, value: str) -> SystemSetting:
    if key not in EDITABLE_KEYS:
        raise ValueError("setting is not editable")
    stored_value = encrypt_secret(value) if EDITABLE_KEYS[key] else value
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        row = SystemSetting(key=key, value=stored_value, is_secret=EDITABLE_KEYS[key])
        db.add(row)
    else:
        row.value = stored_value
        row.is_secret = EDITABLE_KEYS[key]
    db.commit()
    db.refresh(row)
    return row


def list_settings(db: Session):
    rows = db.query(SystemSetting).filter(SystemSetting.key.in_(EDITABLE_KEYS.keys())).order_by(SystemSetting.key).all()
    existing = {r.key: r for r in rows}
    return [
        {
            "key": key,
            "value": (
                "********"
                if EDITABLE_KEYS[key] and key in existing and existing[key].value
                else (existing[key].value if key in existing else "")
            ),
            "is_secret": EDITABLE_KEYS[key],
        }
        for key in EDITABLE_KEYS
    ]

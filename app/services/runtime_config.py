from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.admin_service import get_setting


@dataclass(frozen=True)
class RuntimeConfig:
    ai_api_url: str
    ai_api_key: str
    ai_model: str
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_pro_monthly: str
    stripe_price_health_pro_monthly: str
    stripe_price_premium_monthly: str
    product_pro_monthly_price_minor: int
    product_health_pro_monthly_price_minor: int
    product_premium_monthly_price_minor: int
    wechat_enabled: bool
    wechat_app_id: str
    wechat_mch_id: str
    wechat_api_v3_key: str
    wechat_serial_no: str
    wechat_private_key: str
    wechat_notify_url: str
    alipay_enabled: bool
    alipay_app_id: str
    alipay_private_key: str
    alipay_public_key: str
    alipay_notify_url: str
    alipay_return_url: str
    cors_origins: str


def _int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_runtime_config(db: Session) -> RuntimeConfig:
    return RuntimeConfig(
        ai_api_url=get_setting(db, "ai_api_url", settings.ai_api_url),
        ai_api_key=get_setting(db, "ai_api_key", settings.ai_api_key),
        ai_model=get_setting(db, "ai_model", settings.ai_model),
        stripe_secret_key=get_setting(db, "stripe_secret_key", settings.stripe_secret_key),
        stripe_webhook_secret=get_setting(db, "stripe_webhook_secret", settings.stripe_webhook_secret),
        stripe_price_pro_monthly=get_setting(db, "stripe_price_pro_monthly", settings.stripe_price_pro_monthly),
        stripe_price_health_pro_monthly=get_setting(db, "stripe_price_health_pro_monthly", settings.stripe_price_health_pro_monthly),
        stripe_price_premium_monthly=get_setting(db, "stripe_price_premium_monthly", settings.stripe_price_premium_monthly),
        product_pro_monthly_price_minor=_int(get_setting(db, "product_pro_monthly_price_minor", "999"), 999),
        product_health_pro_monthly_price_minor=_int(get_setting(db, "product_health_pro_monthly_price_minor", "1999"), 1999),
        product_premium_monthly_price_minor=_int(get_setting(db, "product_premium_monthly_price_minor", "2999"), 2999),
        wechat_enabled=_bool(get_setting(db, "wechat_enabled", "false")),
        wechat_app_id=get_setting(db, "wechat_app_id"),
        wechat_mch_id=get_setting(db, "wechat_mch_id"),
        wechat_api_v3_key=get_setting(db, "wechat_api_v3_key"),
        wechat_serial_no=get_setting(db, "wechat_serial_no"),
        wechat_private_key=get_setting(db, "wechat_private_key"),
        wechat_notify_url=get_setting(db, "wechat_notify_url"),
        alipay_enabled=_bool(get_setting(db, "alipay_enabled", "false")),
        alipay_app_id=get_setting(db, "alipay_app_id"),
        alipay_private_key=get_setting(db, "alipay_private_key"),
        alipay_public_key=get_setting(db, "alipay_public_key"),
        alipay_notify_url=get_setting(db, "alipay_notify_url"),
        alipay_return_url=get_setting(db, "alipay_return_url"),
        cors_origins=get_setting(db, "cors_origins", settings.cors_origins),
    )

from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.core.config import settings
from app.services.admin_service import get_setting

@dataclass(frozen=True)
class RuntimeConfig:
    antfu_api_url: str
    antfu_api_key: str
    antfu_model: str
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_pro_monthly: str
    stripe_price_health_pro_monthly: str
    stripe_price_premium_monthly: str
    product_pro_monthly_price_minor: int
    product_health_pro_monthly_price_minor: int
    product_premium_monthly_price_minor: int
    cors_origins: str

def _int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def load_runtime_config(db: Session) -> RuntimeConfig:
    return RuntimeConfig(
        antfu_api_url=get_setting(db, "antfu_api_url", settings.antfu_api_url),
        antfu_api_key=get_setting(db, "antfu_api_key", settings.antfu_api_key),
        antfu_model=get_setting(db, "antfu_model", settings.antfu_model),
        stripe_secret_key=get_setting(db, "stripe_secret_key", settings.stripe_secret_key),
        stripe_webhook_secret=get_setting(db, "stripe_webhook_secret", settings.stripe_webhook_secret),
        stripe_price_pro_monthly=get_setting(db, "stripe_price_pro_monthly", settings.stripe_price_pro_monthly),
        stripe_price_health_pro_monthly=get_setting(db, "stripe_price_health_pro_monthly", settings.stripe_price_health_pro_monthly),
        stripe_price_premium_monthly=get_setting(db, "stripe_price_premium_monthly", settings.stripe_price_premium_monthly),
        product_pro_monthly_price_minor=_int(get_setting(db, "product_pro_monthly_price_minor", "999"), 999),
        product_health_pro_monthly_price_minor=_int(get_setting(db, "product_health_pro_monthly_price_minor", "1999"), 1999),
        product_premium_monthly_price_minor=_int(get_setting(db, "product_premium_monthly_price_minor", "2999"), 2999),
        cors_origins=get_setting(db, "cors_origins", settings.cors_origins),
    )

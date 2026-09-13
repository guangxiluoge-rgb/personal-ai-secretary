from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Personal AI Secretary"
    env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/ai_secretary"
    jwt_secret: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:5173"
    antfu_api_url: str = ""
    antfu_api_key: str = ""
    antfu_model: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_success_url: str = "http://localhost:5173/billing/success"
    stripe_cancel_url: str = "http://localhost:5173/billing/cancel"
    stripe_price_pro_monthly: str = ""
    stripe_price_health_pro_monthly: str = ""
    stripe_price_premium_monthly: str = ""
    wechat_enabled: bool = False
    wechat_app_id: str = ""
    wechat_mch_id: str = ""
    wechat_api_v3_key: str = ""
    wechat_serial_no: str = ""
    wechat_private_key: str = ""
    wechat_notify_url: str = ""
    alipay_enabled: bool = False
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    alipay_public_key: str = ""
    alipay_notify_url: str = ""
    alipay_return_url: str = ""
    alipay_gateway_url: str = "https://openapi.alipay.com/gateway.do"
    storage_dir: str = "/data/uploads"
    max_upload_mb: int = 10
    admin_bootstrap_email: str = ""
    admin_bootstrap_password: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

settings = Settings()

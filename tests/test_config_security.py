import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_development_allows_local_defaults():
    settings = Settings(env="development")
    assert settings.jwt_secret == "CHANGE_ME"


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(env="production")


def test_production_rejects_default_database_url():
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(
            env="production",
            jwt_secret="a" * 48,
        )


def test_production_requires_settings_encryption_key():
    with pytest.raises(ValidationError, match="SETTINGS_ENCRYPTION_KEY"):
        Settings(
            env="production",
            jwt_secret="a" * 48,
            database_url="postgresql+psycopg://prod:secret@example.com/ai_secretary",
        )

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt
import pytest

from app.core import admin_security


def _token(active: bool = True) -> str:
    admin_security.settings.jwt_secret = "test-secret"
    admin_security.settings.jwt_algorithm = "HS256"
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    return jwt.encode({"sub": "7", "admin": True, "exp": exp}, "test-secret", algorithm="HS256")


def test_active_admin_token_is_accepted():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=7, is_active=True)
    credentials = SimpleNamespace(credentials=_token())
    result = admin_security.require_admin_secret(credentials, db)
    assert result["admin"] is True


def test_inactive_admin_token_is_rejected():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    credentials = SimpleNamespace(credentials=_token())
    with pytest.raises(Exception) as exc_info:
        admin_security.require_admin_secret(credentials, db)
    assert getattr(exc_info.value, "status_code", None) == 403

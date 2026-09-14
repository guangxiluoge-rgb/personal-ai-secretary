from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    key = settings.settings_encryption_key.strip()
    if not key:
        raise RuntimeError("SETTINGS_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("SETTINGS_ENCRYPTION_KEY is not a valid Fernet key") from exc


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    if not value.startswith(_PREFIX):
        return value
    token = value[len(_PREFIX) :]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError) as exc:
        raise RuntimeError("stored secret cannot be decrypted") from exc


def is_encrypted(value: str) -> bool:
    return value.startswith(_PREFIX)

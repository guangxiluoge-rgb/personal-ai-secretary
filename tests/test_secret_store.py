from cryptography.fernet import Fernet

from app.core import secret_store


def test_encrypt_and_decrypt_secret(monkeypatch):
    monkeypatch.setattr(secret_store.settings, "settings_encryption_key", Fernet.generate_key().decode())
    encrypted = secret_store.encrypt_secret("gemini-secret")
    assert encrypted.startswith("enc:v1:")
    assert "gemini-secret" not in encrypted
    assert secret_store.decrypt_secret(encrypted) == "gemini-secret"


def test_legacy_plaintext_remains_readable(monkeypatch):
    monkeypatch.setattr(secret_store.settings, "settings_encryption_key", Fernet.generate_key().decode())
    assert secret_store.decrypt_secret("legacy-secret") == "legacy-secret"

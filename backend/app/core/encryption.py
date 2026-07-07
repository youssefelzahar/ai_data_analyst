"""Symmetric encryption for secrets stored at rest (e.g. database passwords).

Credentials for user-created data source connections must never be stored
in plaintext. The Fernet key is derived from the application SECRET_KEY,
so rotating that key invalidates previously stored credentials.
"""

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _build_fernet() -> Fernet:
    secret_key = get_settings().secret_key
    derived_key = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived_key))


def encrypt_secret(plaintext_secret: str) -> str:
    return _build_fernet().encrypt(plaintext_secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_secret: str) -> str:
    return _build_fernet().decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
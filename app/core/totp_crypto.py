"""
AES-256-GCM envelope-style encryption for TOTP secrets at rest.
Production: set TOTP_ENCRYPTION_KEY to a dedicated 32-byte key (base64) from your secrets manager.
"""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _raw_encryption_key() -> bytes:
    if settings.TOTP_ENCRYPTION_KEY:
        s = settings.TOTP_ENCRYPTION_KEY.strip()
        pad = (4 - len(s) % 4) % 4
        padded = s + "=" * pad
        try:
            raw = base64.urlsafe_b64decode(padded)
        except Exception:
            raw = base64.standard_b64decode(padded)
        if len(raw) != 32:
            raise ValueError("TOTP_ENCRYPTION_KEY must decode to exactly 32 bytes")
        return raw
    return hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()


def encrypt_totp_secret(plaintext: str, key_id: str | None = None) -> tuple[bytes, bytes, str]:
    """Return (ciphertext, nonce, key_id)."""
    kid = key_id or settings.TOTP_KEY_ID
    aesgcm = AESGCM(_raw_encryption_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), associated_data=kid.encode("utf-8"))
    return ciphertext, nonce, kid


def decrypt_totp_secret(ciphertext: bytes, nonce: bytes, key_id: str) -> str:
    aesgcm = AESGCM(_raw_encryption_key())
    plain = aesgcm.decrypt(nonce, ciphertext, associated_data=key_id.encode("utf-8"))
    return plain.decode("utf-8")

"""
AES-256-GCM envelope-style encryption for TOTP secrets at rest.
Production: set TOTP_ENCRYPTION_KEY to a dedicated 32-byte key (base64) from your secrets manager.
If the env value is missing, invalid base64, or not exactly 32 bytes after decode, we derive the
key from SECRET_KEY (same as omitting TOTP_ENCRYPTION_KEY) so deploys with typos do not 500 MFA.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

logger = logging.getLogger(__name__)


def _derive_key_from_secret() -> bytes:
    return hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()


def _raw_encryption_key() -> bytes:
    if not settings.TOTP_ENCRYPTION_KEY:
        return _derive_key_from_secret()

    s = settings.TOTP_ENCRYPTION_KEY.strip()
    pad = (4 - len(s) % 4) % 4
    padded = s + "=" * pad
    try:
        try:
            raw = base64.urlsafe_b64decode(padded)
        except Exception:
            raw = base64.standard_b64decode(padded)
    except Exception:
        logger.warning(
            "TOTP_ENCRYPTION_KEY is not valid base64; using SECRET_KEY-derived TOTP encryption key. "
            "Remove TOTP_ENCRYPTION_KEY or set a 32-byte key as URL-safe base64 (see docs)."
        )
        return _derive_key_from_secret()

    if len(raw) != 32:
        logger.warning(
            "TOTP_ENCRYPTION_KEY decodes to %d bytes, not 32; using SECRET_KEY-derived key instead.",
            len(raw),
        )
        return _derive_key_from_secret()

    return raw


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

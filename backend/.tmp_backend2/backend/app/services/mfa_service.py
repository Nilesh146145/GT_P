"""
TOTP MFA helpers — issuer and timing from ``settings`` (no hardcoded issuer).
"""

import secrets
from typing import List, Optional, Tuple

import pyotp

from app.core.config import settings
from app.core.security import get_password_hash, verify_password


def generate_base32_secret() -> str:
    """Cryptographically strong base32 secret for TOTP."""
    return pyotp.random_base32()


def totp_for_secret(secret: str) -> pyotp.TOTP:
    """RFC 6238 TOTP with interval from ``TOTP_INTERVAL_SECONDS`` (default 30s)."""
    return pyotp.TOTP(secret, interval=settings.TOTP_INTERVAL_SECONDS)


def build_provisioning_uri(*, secret: str, account_email: str) -> str:
    """otpauth:// URL for authenticator apps; issuer from ``TOTP_ISSUER``."""
    totp = totp_for_secret(secret)
    return totp.provisioning_uri(name=account_email, issuer_name=settings.TOTP_ISSUER)


def verify_totp_code(secret: str, code: str, *, valid_window: int = 1) -> bool:
    """
    Verify a TOTP code. ``valid_window`` allows ±N intervals for clock skew (default ±1 step).
    Rejects empty or non-numeric-looking codes.
    """
    if not code or not code.strip():
        return False
    try:
        totp = totp_for_secret(secret)
        return bool(totp.verify(code.strip(), valid_window=valid_window))
    except Exception:
        return False


def generate_recovery_code_sets(count: int) -> Tuple[List[str], List[str]]:
    """
    FSD §3.3.2 — ``count`` single-use recovery codes (plaintext + bcrypt hashes for storage).
    Plaintext is shown once to the user; only hashes are persisted.
    """
    plain = [secrets.token_hex(5).upper() for _ in range(count)]
    hashed = [get_password_hash(p) for p in plain]
    return plain, hashed


def match_recovery_code(plain: str, stored_hashes: List[str]) -> Optional[int]:
    """
    Return index of the matching hash if ``plain`` matches one unused hash, else ``None``.
    """
    if not plain or not plain.strip() or not stored_hashes:
        return None
    candidate = plain.strip().upper()
    for i, h in enumerate(stored_hashes):
        try:
            if verify_password(candidate, h):
                return i
        except Exception:
            continue
    return None

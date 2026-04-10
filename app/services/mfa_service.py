"""
Production TOTP MFA (RFC 6238): setup, verify, recovery, disable.
"""

from __future__ import annotations

import base64
import io
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
from bson import ObjectId
from cryptography.exceptions import InvalidTag
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.database import (
    get_mfa_audit_collection,
    get_mfa_recovery_codes_collection,
    get_mfa_setup_pending_collection,
    get_totp_credentials_collection,
    get_users_collection,
)
from app.core.rate_limit import check_rate_limit
from app.core.totp_crypto import decrypt_totp_secret, encrypt_totp_secret
from app.core.security import get_password_hash, verify_password
from app.services.reviewer import reviewer_auth_service

logger = logging.getLogger(__name__)


def qr_png_base64_for_otpauth_uri(otpauth_uri: str) -> str | None:
    """
    Render the provisioning URI as a PNG (base64, no data-URL prefix).
    Lets clients use <img src={`data:image/png;base64,${qrCodePngBase64}`} /> without
    client-side QR libraries or third-party chart URLs (often blocked in production).
    """
    if not otpauth_uri or not otpauth_uri.strip().startswith("otpauth://"):
        return None
    try:
        import segno

        qr = segno.make(otpauth_uri.strip(), error="m")
        buf = io.BytesIO()
        qr.save(buf, kind="png", scale=6)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        logger.exception("MFA QR PNG generation failed (segno)")
        return None


def _decrypt_stored_totp_secret(
    ciphertext: bytes,
    nonce: bytes,
    key_id: str,
    *,
    context: str,
) -> str:
    """
    Decrypt TOTP material; turn AES-GCM failures into a client-safe error.
    InvalidTag often means SECRET_KEY / TOTP_ENCRYPTION_KEY changed after enrollment — str(exc) is empty,
    which previously produced HTTP 500 with blank detail.
    """
    try:
        return decrypt_totp_secret(ciphertext, nonce, key_id)
    except InvalidTag:
        logger.error(
            "TOTP decrypt failed (%s): AES-GCM authentication failed — check SECRET_KEY/TOTP_ENCRYPTION_KEY vs enrollment time",
            context,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MFA_SECRET_UNREADABLE",
                "message": (
                    "The stored MFA secret cannot be decrypted. This usually means SECRET_KEY or "
                    "TOTP_ENCRYPTION_KEY was changed after MFA was enabled. Clear MFA for this user in the "
                    "database (totp credentials + mfa flags) or restore the previous keys, then enroll again."
                ),
            },
        ) from None


def _as_utc_aware(dt: datetime) -> datetime:
    """MongoDB often returns naive UTC datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _norm_recovery_code(raw: str) -> str:
    s = re.sub(r"\s+", "", raw.strip().upper())
    return s.replace("-", "")


def _format_recovery_code_for_display(raw_hex: str) -> str:
    return "-".join(raw_hex[i : i + 4] for i in range(0, len(raw_hex), 4)).upper()


async def _audit(
    event: str,
    user_id: str,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    col = get_mfa_audit_collection()
    await col.insert_one({
        "user_id": user_id,
        "event": event,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": datetime.now(timezone.utc),
    })


async def _revoke_all_sessions(user_id: str) -> None:
    from app.core.database import get_sessions_collection

    sessions_col = get_sessions_collection()
    await sessions_col.update_many(
        {"user_id": user_id, "revoked_at": None},
        {"$set": {"revoked_at": datetime.now(timezone.utc)}},
    )


async def init_setup(
    user: dict,
    *,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> tuple[str, str]:
    """Create pending encrypted secret; return (otpauth_uri, secret_base32)."""
    if user.get("mfa_enabled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MFA_ALREADY_ENABLED", "message": "MFA is already enabled for this account."},
        )

    await check_rate_limit(
        scope="mfa_setup_init",
        bucket=user["id"],
        max_events=20,
        window_seconds=3600,
    )

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    otpauth_uri = totp.provisioning_uri(
        name=user["email"],
        issuer_name=settings.TOTP_ISSUER,
    )

    ciphertext, nonce, key_id = encrypt_totp_secret(secret)
    pending_col = get_mfa_setup_pending_collection()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.MFA_SETUP_PENDING_MINUTES)

    await pending_col.delete_many({"user_id": user["id"]})
    await pending_col.insert_one({
        "user_id": user["id"],
        "secret_ciphertext": ciphertext,
        "encryption_iv": nonce,
        "secret_key_id": key_id,
        "created_at": now,
        "expires_at": expires_at,
    })

    await _audit("enroll_start", user["id"], ip_address=ip_address, user_agent=user_agent)
    return otpauth_uri, secret


async def _load_pending_secret(user_id: str) -> str:
    pending_col = get_mfa_setup_pending_collection()
    doc = await pending_col.find_one({"user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MFA_SETUP_EXPIRED", "message": "Start MFA setup again."},
        )
    if _as_utc_aware(doc["expires_at"]) < datetime.now(timezone.utc):
        await pending_col.delete_one({"_id": doc["_id"]})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MFA_SETUP_EXPIRED", "message": "Setup session expired. Start again."},
        )
    return _decrypt_stored_totp_secret(
        doc["secret_ciphertext"],
        doc["encryption_iv"],
        doc["secret_key_id"],
        context="setup_pending",
    )


async def confirm_setup(
    user: dict,
    code: str,
    *,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> list[str]:
    """Verify TOTP, persist encrypted secret, recovery codes; return plaintext codes once."""
    await check_rate_limit(
        scope="mfa_setup_confirm",
        bucket=user["id"],
        max_events=settings.MFA_VERIFY_MAX_ATTEMPTS_PER_MINUTE,
        window_seconds=60,
    )

    if user.get("mfa_enabled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MFA_ALREADY_ENABLED", "message": "MFA is already enabled."},
        )

    plain_secret = await _load_pending_secret(user["id"])
    totp = pyotp.TOTP(plain_secret)
    if not totp.verify(code.strip().replace(" ", ""), valid_window=1):
        await _audit("enroll_fail", user["id"], ip_address=ip_address, user_agent=user_agent)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TOTP", "message": "Invalid verification code."},
        )

    ciphertext, nonce, key_id = encrypt_totp_secret(plain_secret)
    totp_col = get_totp_credentials_collection()
    now = datetime.now(timezone.utc)
    await totp_col.delete_many({"user_id": user["id"]})
    await totp_col.insert_one({
        "user_id": user["id"],
        "secret_ciphertext": ciphertext,
        "encryption_iv": nonce,
        "secret_key_id": key_id,
        "updated_at": now,
        "created_at": now,
    })

    await get_mfa_setup_pending_collection().delete_many({"user_id": user["id"]})

    recovery_plain: list[str] = []
    recovery_col = get_mfa_recovery_codes_collection()
    await recovery_col.delete_many({"user_id": user["id"], "used_at": None})
    inserts = []
    for _ in range(settings.MFA_RECOVERY_CODE_COUNT):
        raw = secrets.token_hex(8)
        display = _format_recovery_code_for_display(raw)
        recovery_plain.append(display)
        inserts.append({
            "user_id": user["id"],
            "code_hash": get_password_hash(raw.lower()),
            "used_at": None,
            "created_at": now,
        })
    if inserts:
        await recovery_col.insert_many(inserts)

    users_col = get_users_collection()
    await users_col.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {
            "mfa_enabled": True,
            "mfa_enrolled_at": now,
            "updated_at": now,
        }},
    )

    await _audit("enroll_complete", user["id"], ip_address=ip_address, user_agent=user_agent)
    return recovery_plain


async def verify_totp_code(
    user_id: str,
    code: str,
    *,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> None:
    await check_rate_limit(
        scope="mfa_verify",
        bucket=user_id,
        max_events=settings.MFA_VERIFY_MAX_ATTEMPTS_PER_MINUTE,
        window_seconds=60,
    )
    if ip_address:
        await check_rate_limit(
            scope="mfa_verify_ip",
            bucket=ip_address,
            max_events=settings.MFA_VERIFY_MAX_ATTEMPTS_PER_MINUTE * 3,
            window_seconds=60,
        )

    totp_col = get_totp_credentials_collection()
    doc = await totp_col.find_one({"user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MFA_NOT_CONFIGURED", "message": "MFA is not configured."},
        )

    secret = _decrypt_stored_totp_secret(
        doc["secret_ciphertext"],
        doc["encryption_iv"],
        doc["secret_key_id"],
        context="verify_totp",
    )
    totp = pyotp.TOTP(secret)
    if not totp.verify(code.strip().replace(" ", ""), valid_window=1):
        await _audit("verify_fail", user_id, ip_address=ip_address, user_agent=user_agent)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TOTP", "message": "Invalid verification code."},
        )

    await _audit("verify_ok", user_id, ip_address=ip_address, user_agent=user_agent)
    now = datetime.now(timezone.utc)
    await get_users_collection().update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"mfa_last_verified_at": now}},
    )


async def consume_recovery_code(
    user_id: str,
    recovery_code: str,
    *,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> None:
    await check_rate_limit(
        scope="mfa_recovery",
        bucket=user_id,
        max_events=settings.MFA_RECOVERY_MAX_ATTEMPTS_PER_HOUR,
        window_seconds=3600,
    )

    normalized = _norm_recovery_code(recovery_code).lower()
    if len(normalized) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_RECOVERY_CODE", "message": "Invalid recovery code."},
        )

    recovery_col = get_mfa_recovery_codes_collection()
    cursor = recovery_col.find({"user_id": user_id, "used_at": None})
    now = datetime.now(timezone.utc)
    async for row in cursor:
        raw_stored = row["code_hash"]
        if verify_password(normalized, raw_stored):
            upd = await recovery_col.update_one(
                {"_id": row["_id"], "used_at": None},
                {"$set": {"used_at": now}},
            )
            if upd.modified_count == 1:
                await _audit("recovery_used", user_id, ip_address=ip_address, user_agent=user_agent)
                return
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "RECOVERY_CODE_USED", "message": "This recovery code was already used."},
            )

    await _audit("recovery_fail", user_id, ip_address=ip_address, user_agent=user_agent)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "INVALID_RECOVERY_CODE", "message": "Invalid recovery code."},
    )


async def disable_mfa_for_user(
    user: dict,
    password: str,
    *,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> None:
    role = reviewer_auth_service.normalize_role(user.get("role"))
    if role == "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "MFA_POLICY_FORBIDDEN", "message": "Enterprise accounts cannot disable MFA."},
        )
    if role == "reviewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "MFA_POLICY_FORBIDDEN", "message": "Reviewer accounts cannot disable MFA."},
        )

    if not user.get("hashed_password"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PASSWORD_REQUIRED", "message": "Password confirmation required."},
        )

    if not verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PASSWORD", "message": "Invalid password."},
        )

    if not user.get("mfa_enabled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MFA_NOT_ENABLED", "message": "MFA is not enabled."},
        )

    uid = user["id"]
    await get_totp_credentials_collection().delete_many({"user_id": uid})
    await get_mfa_recovery_codes_collection().delete_many({"user_id": uid})
    await get_mfa_setup_pending_collection().delete_many({"user_id": uid})

    await get_users_collection().update_one(
        {"_id": ObjectId(uid)},
        {"$set": {
            "mfa_enabled": False,
            "mfa_enrolled_at": None,
            "mfa_last_verified_at": None,
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    await _revoke_all_sessions(uid)
    await _audit("disable", uid, ip_address=ip_address, user_agent=user_agent)


def mfa_enrollment_required(user: dict) -> bool:
    return reviewer_auth_service.mfa_enrollment_required(user)


def needs_mfa_verify_after_login(user: dict) -> bool:
    return bool(user.get("mfa_enabled"))


async def load_user_by_id(user_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    col = get_users_collection()
    u = await col.find_one({"_id": oid})
    if u:
        u["id"] = str(u["_id"])
    return u

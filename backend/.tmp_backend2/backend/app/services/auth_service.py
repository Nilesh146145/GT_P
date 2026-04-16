"""
Auth Service
────────────
Business logic for login, session management, token refresh, and logout.

Aligned with FSD GWIP Enterprise Portal §3 (Authentication, Session & MFA).
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.auth_fsd import (
    AUTH_001_NO_ACCOUNT,
    AUTH_003_LOCKED,
    AUTH_004_TOTP_INVALID,
    AUTH_005_TOTP_REPLAY,
    AUTH_007_PORTAL,
    AUTH_008_DEACTIVATED,
    PORTAL_ROLES,
    err_detail,
    wrong_password_detail,
)
from app.core.config import settings
from app.core.database import get_sessions_collection, get_users_collection
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.schemas.auth import (
    AuthUser,
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    MfaRequiredLoginResponse,
    MfaSetupResponse,
    MfaStatusResponse,
    SessionItem,
    SessionListResponse,
    TokenPair,
    ValidateResponse,
)
from app.services import mfa_service

logger = logging.getLogger(__name__)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _to_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_account_locked(user: dict) -> bool:
    lu = _to_utc_aware(user.get("account_locked_until"))
    if lu is None:
        return False
    return lu > _now_utc()


async def _clear_expired_lock(col, oid: ObjectId, user: dict) -> None:
    lu = _to_utc_aware(user.get("account_locked_until"))
    if lu is None or lu > _now_utc():
        return
    await col.update_one(
        {"_id": oid},
        {
            "$unset": {"account_locked_until": ""},
            "$set": {"failed_password_attempts": 0, "failed_totp_attempts": 0},
        },
    )
    user["account_locked_until"] = None
    user["failed_password_attempts"] = 0
    user["failed_totp_attempts"] = 0


async def _trim_sessions(sessions_col, user_id: str, now: datetime) -> None:
    """FSD §3.4 — max concurrent sessions; revoke oldest when over limit."""
    max_s = settings.MAX_CONCURRENT_SESSIONS
    while True:
        count = await sessions_col.count_documents({"user_id": user_id, "revoked_at": None})
        if count < max_s:
            break
        oldest = await sessions_col.find_one(
            {"user_id": user_id, "revoked_at": None},
            sort=[("created_at", 1)],
        )
        if oldest is None:
            break
        await sessions_col.update_one({"_id": oldest["_id"]}, {"$set": {"revoked_at": now}})


def _mfa_display_flag(user: dict) -> bool:
    return bool(user.get("is_mfa_enabled", user.get("mfa_enabled", False)))


def _user_requires_totp_step(user: dict) -> bool:
    """
    True when login must stop after password and require TOTP (or recovery code).

    Requires a persisted ``mfa_secret`` and MFA enabled flags (``is_mfa_enabled`` / ``mfa_enabled``).
    Matches DB field semantics; not the same as pending ``mfa_temp_secret`` enrollment.
    """
    if not user.get("mfa_secret"):
        return False
    return bool(user.get("is_mfa_enabled") or user.get("mfa_enabled"))


def _portal_role_ok(user: dict) -> bool:
    r = user.get("role") or "enterprise"
    return r in PORTAL_ROLES


def current_user_public_dict(user: dict) -> dict:
    uid = str(user.get("id") or user["_id"])
    return CurrentUserResponse(
        id=uid,
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name", ""),
        email=user["email"],
        email_verified=user.get("email_verified", False),
        phone_verified=user.get("phone_verified", False),
        role=user.get("role", "enterprise"),
        requires_password_change=user.get("requires_password_change", False),
        is_first_login=user.get("is_first_login", False),
        is_mfa_enabled=bool(user.get("is_mfa_enabled", user.get("mfa_enabled", False))),
    ).model_dump(by_alias=True)


def _build_auth_user(user: dict) -> AuthUser:
    return AuthUser(
        id=str(user["_id"]),
        email=user["email"],
        firstName=user.get("first_name", ""),
        lastName=user.get("last_name", ""),
        role=user.get("role", "enterprise"),
        provider=user.get("provider", "credentials"),
        phoneVerified=user.get("phone_verified", False),
        emailVerified=user.get("email_verified", False),
        isFirstLogin=user.get("is_first_login", False),
        isMfaEnabled=_mfa_display_flag(user),
    )


async def _issue_login_tokens(
    user: dict,
    ip_address: Optional[str],
    user_agent: Optional[str],
    remember_me: bool,
    auth_method: str = "password",
) -> LoginResponse:
    col = get_users_collection()
    user_id = str(user["_id"])
    access_token = create_access_token({"sub": user_id, "role": user.get("role", "enterprise")})

    rdays = settings.REFRESH_TOKEN_EXPIRE_DAYS if remember_me else settings.REFRESH_TOKEN_EXPIRE_DAYS_SHORT
    refresh_token = create_refresh_token(
        {"sub": user_id, "role": user.get("role", "enterprise")},
        expires_delta=timedelta(days=rdays),
    )

    sessions_col = get_sessions_collection()
    now = _now_utc()
    expires_at = now + timedelta(days=rdays)
    await _trim_sessions(sessions_col, user_id, now)
    await sessions_col.insert_one({
        "user_id": user_id,
        "refresh_token_hash": _hash_token(refresh_token),
        "auth_method": auth_method,
        "user_agent": user_agent,
        "ip_address": ip_address,
        "created_at": now,
        "expires_at": expires_at,
        "revoked_at": None,
    })

    await col.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "last_login_at": now,
                "failed_password_attempts": 0,
                "failed_totp_attempts": 0,
            }
        },
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_build_auth_user(user),
    )


async def login_user(
    payload: LoginRequest,
    ip_address: Optional[str],
    user_agent: Optional[str],
    remember_me: bool = False,
) -> Union[LoginResponse, MfaRequiredLoginResponse]:
    col = get_users_collection()
    user = await col.find_one({"email": payload.email.lower()})

    if not user or not user.get("hashed_password"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_detail("AUTH-001", AUTH_001_NO_ACCOUNT),
        )

    if user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err_detail("AUTH-008", AUTH_008_DEACTIVATED),
        )

    oid = user["_id"]
    await _clear_expired_lock(col, oid, user)

    if _is_account_locked(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_detail("AUTH-003", AUTH_003_LOCKED),
        )

    if not _portal_role_ok(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err_detail("AUTH-007", AUTH_007_PORTAL),
        )

    if not verify_password(payload.password, user["hashed_password"]):
        n = int(user.get("failed_password_attempts") or 0) + 1
        max_f = settings.AUTH_PASSWORD_FAILS_BEFORE_LOCKOUT
        if n >= max_f:
            lock_until = _now_utc() + timedelta(minutes=settings.AUTH_LOCKOUT_MINUTES)
            await col.update_one(
                {"_id": oid},
                {"$set": {"account_locked_until": lock_until, "failed_password_attempts": 0}},
            )
            logger.info("[AUTH] Account locked after password failures: %s", user.get("email"))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=err_detail("AUTH-003", AUTH_003_LOCKED),
            )
        await col.update_one({"_id": oid}, {"$set": {"failed_password_attempts": n}})
        remaining = max_f - n
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=wrong_password_detail(remaining),
        )

    if user.get("sso_only"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SSO_REQUIRED", "provider_hint": user.get("provider", "enterprise-sso")},
        )

    await col.update_one(
        {"_id": oid},
        {
            "$set": {"failed_password_attempts": 0},
            "$unset": {"mfa_last_consumed_totp_period": ""},
        },
    )

    if _user_requires_totp_step(user):
        return MfaRequiredLoginResponse(email=user["email"])

    return await _issue_login_tokens(user, ip_address, user_agent, remember_me)


async def validate_credentials(payload: LoginRequest) -> ValidateResponse:
    col = get_users_collection()
    user = await col.find_one({"email": payload.email.lower()})

    if not user or not user.get("hashed_password"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_detail("AUTH-001", AUTH_001_NO_ACCOUNT),
        )

    if user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err_detail("AUTH-008", AUTH_008_DEACTIVATED),
        )

    oid = user["_id"]
    await _clear_expired_lock(col, oid, user)
    if _is_account_locked(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_detail("AUTH-003", AUTH_003_LOCKED),
        )

    if not _portal_role_ok(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err_detail("AUTH-007", AUTH_007_PORTAL),
        )

    if not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=wrong_password_detail(None),
        )

    return ValidateResponse(valid=True)


async def refresh_session(refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    sessions_col = get_sessions_collection()
    session = await sessions_col.find_one({
        "refresh_token_hash": _hash_token(refresh_token),
        "revoked_at": None,
    })
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found or revoked")

    users_col = get_users_collection()
    try:
        uid_oid = ObjectId(payload["sub"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    u = await users_col.find_one({"_id": uid_oid})
    if u is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if u.get("is_active") is False:
        await logout_session(refresh_token)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err_detail("AUTH-008", AUTH_008_DEACTIVATED),
        )

    access_token = create_access_token({"sub": payload["sub"], "role": payload.get("role")})
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


async def logout_session(refresh_token: str) -> None:
    sessions_col = get_sessions_collection()
    await sessions_col.update_one(
        {"refresh_token_hash": _hash_token(refresh_token)},
        {"$set": {"revoked_at": _now_utc()}},
    )


async def logout_all_sessions(user_id: str) -> None:
    sessions_col = get_sessions_collection()
    await sessions_col.update_many(
        {"user_id": user_id, "revoked_at": None},
        {"$set": {"revoked_at": _now_utc()}},
    )


async def revoke_session_by_id(session_id: str, user_id: str) -> None:
    sessions_col = get_sessions_collection()
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID")

    session = await sessions_col.find_one({"_id": oid, "user_id": user_id})
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    await sessions_col.update_one({"_id": oid}, {"$set": {"revoked_at": _now_utc()}})


async def list_sessions(user_id: str) -> SessionListResponse:
    sessions_col = get_sessions_collection()
    cursor = sessions_col.find({"user_id": user_id, "revoked_at": None})
    sessions = []
    async for s in cursor:
        sessions.append(SessionItem(
            id=str(s["_id"]),
            auth_method=s.get("auth_method", "password"),
            user_agent=s.get("user_agent"),
            ip_address=str(s["ip_address"]) if s.get("ip_address") else None,
            created_at=s["created_at"],
            expires_at=s["expires_at"],
        ))
    return SessionListResponse(sessions=sessions)


async def start_mfa_setup(user_id: str, email: str) -> MfaSetupResponse:
    if not (settings.TOTP_ISSUER or "").strip():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TOTP_ISSUER is not configured.",
        )

    col = get_users_collection()
    try:
        oid = ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user.") from exc

    user = await col.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user.get("mfa_secret") and (user.get("is_mfa_enabled") or user.get("mfa_enabled")):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFA is already enabled. Disable it before re-enrolling.",
        )

    secret = mfa_service.generate_base32_secret()
    now = _now_utc()
    otpauth_url = mfa_service.build_provisioning_uri(secret=secret, account_email=email)

    await col.update_one(
        {"_id": oid},
        {
            "$set": {
                "mfa_temp_secret": secret,
                "mfa_temp_secret_set_at": now,
                "updated_at": now,
            }
        },
    )

    return MfaSetupResponse(secret=secret, otpauth_url=otpauth_url)


def _temp_secret_age_seconds(set_at: Optional[datetime]) -> float:
    if set_at is None:
        return float("inf")
    now = _now_utc()
    set_at = _to_utc_aware(set_at)
    if set_at is None:
        return float("inf")
    return (now - set_at).total_seconds()


async def verify_mfa_setup(user_id: str, code: str) -> List[str]:
    """
    Confirm TOTP enrollment; persist secret and return one-time recovery codes (FSD §3.3.2).
    """
    col = get_users_collection()
    try:
        oid = ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user.") from exc

    user = await col.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    temp = user.get("mfa_temp_secret")
    if not temp or not isinstance(temp, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No MFA setup in progress. Call POST /api/v1/auth/mfa/setup/init first.",
        )

    if _temp_secret_age_seconds(user.get("mfa_temp_secret_set_at")) > settings.OTP_EXPIRE_SECONDS:
        await col.update_one(
            {"_id": oid},
            {
                "$unset": {"mfa_temp_secret": "", "mfa_temp_secret_set_at": ""},
                "$set": {"updated_at": _now_utc()},
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup expired. Start again with POST /api/v1/auth/mfa/setup/init.",
        )

    if not mfa_service.verify_totp_code(temp, code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_detail("AUTH-004", AUTH_004_TOTP_INVALID),
        )

    n_codes = settings.MFA_RECOVERY_CODE_COUNT
    plain_codes, hashed_codes = mfa_service.generate_recovery_code_sets(n_codes)

    now = _now_utc()
    role = user.get("role") or "enterprise"
    update_doc: dict = {
        "mfa_secret": temp,
        "is_mfa_enabled": True,
        "mfa_enabled": True,
        "mfa_recovery_hashes": hashed_codes,
        "updated_at": now,
    }
    if role == "reviewer" and not user.get("requires_password_change", False):
        update_doc["is_first_login"] = False

    await col.update_one(
        {"_id": oid},
        {
            "$set": update_doc,
            "$unset": {
                "mfa_temp_secret": "",
                "mfa_temp_secret_set_at": "",
                "mfa_last_consumed_totp_period": "",
            },
        },
    )

    return plain_codes


async def verify_login_mfa(
    email: str,
    code: Optional[str],
    recovery_code: Optional[str],
    remember_me: bool,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> LoginResponse:
    col = get_users_collection()
    user = await col.find_one({"email": email.lower()})

    if not user or not user.get("mfa_secret"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_detail("AUTH-001", AUTH_001_NO_ACCOUNT),
        )

    if user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err_detail("AUTH-008", AUTH_008_DEACTIVATED),
        )

    if not _portal_role_ok(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err_detail("AUTH-007", AUTH_007_PORTAL),
        )

    oid = user["_id"]
    await _clear_expired_lock(col, oid, user)

    if _is_account_locked(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_detail("AUTH-003", AUTH_003_LOCKED),
        )

    if not _user_requires_totp_step(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is not required for this account.",
        )

    if recovery_code and recovery_code.strip():
        hashes = user.get("mfa_recovery_hashes") or []
        if not isinstance(hashes, list):
            hashes = []
        idx = mfa_service.match_recovery_code(recovery_code, hashes)
        if idx is None:
            n = int(user.get("failed_totp_attempts") or 0) + 1
            max_t = settings.AUTH_TOTP_FAILS_BEFORE_LOCKOUT
            if n >= max_t:
                lock_until = _now_utc() + timedelta(minutes=settings.AUTH_LOCKOUT_MINUTES)
                await col.update_one(
                    {"_id": oid},
                    {"$set": {"account_locked_until": lock_until, "failed_totp_attempts": 0}},
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=err_detail("AUTH-003", AUTH_003_LOCKED),
                )
            await col.update_one({"_id": oid}, {"$set": {"failed_totp_attempts": n}})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=err_detail("AUTH-004", AUTH_004_TOTP_INVALID),
            )
        new_hashes = [h for i, h in enumerate(hashes) if i != idx]
        await col.update_one(
            {"_id": oid},
            {"$set": {"mfa_recovery_hashes": new_hashes, "failed_totp_attempts": 0}},
        )
        return await _issue_login_tokens(
            user, ip_address, user_agent, remember_me, auth_method="totp",
        )

    # TOTP path
    interval = settings.TOTP_INTERVAL_SECONDS
    period = int(time.time()) // interval
    last_p = user.get("mfa_last_consumed_totp_period")
    if last_p is not None and last_p == period:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_detail("AUTH-005", AUTH_005_TOTP_REPLAY),
        )

    if not code or not mfa_service.verify_totp_code(user["mfa_secret"], code):
        if not code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=err_detail("AUTH-004", AUTH_004_TOTP_INVALID),
            )
        n = int(user.get("failed_totp_attempts") or 0) + 1
        max_t = settings.AUTH_TOTP_FAILS_BEFORE_LOCKOUT
        if n >= max_t:
            lock_until = _now_utc() + timedelta(minutes=settings.AUTH_LOCKOUT_MINUTES)
            await col.update_one(
                {"_id": oid},
                {"$set": {"account_locked_until": lock_until, "failed_totp_attempts": 0}},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=err_detail("AUTH-003", AUTH_003_LOCKED),
            )
        await col.update_one({"_id": oid}, {"$set": {"failed_totp_attempts": n}})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_detail("AUTH-004", AUTH_004_TOTP_INVALID),
        )

    await col.update_one(
        {"_id": oid},
        {"$set": {"mfa_last_consumed_totp_period": period, "failed_totp_attempts": 0}},
    )
    return await _issue_login_tokens(
        user, ip_address, user_agent, remember_me, auth_method="totp",
    )


async def _require_password_and_totp_for_mfa_action(user_id: str, password: str, code: str) -> dict:
    """Load user, verify password and current TOTP; return the user document."""
    col = get_users_collection()
    try:
        oid = ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user.") from exc

    user = await col.find_one({"_id": oid})
    if not user or not user.get("hashed_password"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if not _user_requires_totp_step(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled for this account.",
        )

    if not verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=wrong_password_detail(None),
        )

    if not mfa_service.verify_totp_code(user["mfa_secret"], code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_detail("AUTH-004", AUTH_004_TOTP_INVALID),
        )

    return user


async def disable_mfa(user_id: str, password: str, code: str) -> None:
    """
    Turn off TOTP MFA and clear recovery codes.

    Reviewer accounts cannot disable MFA (portal policy).
    All refresh sessions are revoked (FSD §3.4).
    """
    user = await _require_password_and_totp_for_mfa_action(user_id, password, code)
    if (user.get("role") or "enterprise") == "reviewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer accounts cannot disable MFA.",
        )

    col = get_users_collection()
    oid = user["_id"]
    now = _now_utc()
    await col.update_one(
        {"_id": oid},
        {
            "$set": {
                "is_mfa_enabled": False,
                "mfa_enabled": False,
                "updated_at": now,
            },
            "$unset": {
                "mfa_secret": "",
                "mfa_recovery_hashes": "",
                "mfa_last_consumed_totp_period": "",
                "mfa_temp_secret": "",
                "mfa_temp_secret_set_at": "",
            },
        },
    )
    await logout_all_sessions(user_id)


async def regenerate_mfa_recovery_codes(user_id: str, password: str, code: str) -> List[str]:
    """Replace stored recovery hashes; return new plaintext codes once (FSD §3.3.2)."""
    user = await _require_password_and_totp_for_mfa_action(user_id, password, code)
    col = get_users_collection()
    oid = user["_id"]
    n_codes = settings.MFA_RECOVERY_CODE_COUNT
    plain_codes, hashed_codes = mfa_service.generate_recovery_code_sets(n_codes)
    await col.update_one(
        {"_id": oid},
        {"$set": {"mfa_recovery_hashes": hashed_codes, "updated_at": _now_utc()}},
    )
    return plain_codes


async def cancel_mfa_setup(user_id: str) -> None:
    """Abandon an in-progress enrollment (clears ``mfa_temp_secret`` only)."""
    col = get_users_collection()
    try:
        oid = ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user.") from exc

    user = await col.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if not user.get("mfa_temp_secret"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No MFA enrollment in progress.",
        )

    await col.update_one(
        {"_id": oid},
        {
            "$unset": {"mfa_temp_secret": "", "mfa_temp_secret_set_at": ""},
            "$set": {"updated_at": _now_utc()},
        },
    )


async def get_mfa_status(user_id: str) -> MfaStatusResponse:
    """Return MFA flags and recovery-code count for the security settings UI."""
    col = get_users_collection()
    try:
        oid = ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user.") from exc

    user = await col.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    hashes = user.get("mfa_recovery_hashes") or []
    n_remaining = len(hashes) if isinstance(hashes, list) else 0
    enabled = _user_requires_totp_step(user)
    pending = bool(user.get("mfa_temp_secret"))

    return MfaStatusResponse(
        mfa_enabled=enabled,
        pending_enrollment=pending,
        recovery_codes_remaining=n_remaining,
    )

"""
Auth Service
────────────
Business logic for login, session management, token refresh, and logout.

Collections:
  users    — user accounts
  sessions — active refresh token sessions (TTL via expires_at index)
"""


import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.database import get_sessions_collection, get_users_collection
from app.core.security import (
    create_access_token,
    create_mfa_pending_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.schemas.auth import (
    AuthUser,
    LoginRequest,
    LoginResponse,
    MfaPendingLoginResponse,
    SessionItem,
    SessionListResponse,
    TokenPair,
    ValidateResponse,
)
from app.services.reviewer import reviewer_auth_service

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


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
        **reviewer_auth_service.auth_user_flags(user),
    )


# ── Full session (post-MFA or no MFA) ─────────────────────────────────────────

async def issue_full_login_response(
    user: dict,
    ip_address: Optional[str],
    user_agent: Optional[str],
    *,
    auth_method: str = "password",
    amr: Optional[list[str]] = None,
) -> LoginResponse:
    """Mint access + refresh, persist refresh session, return login payload."""
    user_id = str(user["_id"])
    role = user.get("role", "enterprise")
    amr_list = amr or ["pwd"]
    access_token = create_access_token(
        {"sub": user_id, "role": role},
        mfa_verified=True,
        amr=amr_list,
    )
    refresh_token = create_refresh_token({"sub": user_id, "role": role}, mfa_verified=True)

    sessions_col = get_sessions_collection()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
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

    users_col = get_users_collection()
    await users_col.update_one({"_id": user["_id"]}, {"$set": {"last_login_at": now}})

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_build_auth_user(user),
    )


# ── Login ─────────────────────────────────────────────────────────────────────

async def login_user(
    payload: LoginRequest,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> Union[LoginResponse, MfaPendingLoginResponse]:
    col = get_users_collection()
    user = await col.find_one({"email": payload.email.lower()})

    if not user or not user.get("hashed_password"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NO_ACCOUNT", "message": "We couldn't find an account associated with this email."},
        )

    if not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "WRONG_PASSWORD", "message": "The password you entered is incorrect."},
        )

    # SSO-only accounts
    if user.get("sso_only"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SSO_REQUIRED", "provider_hint": user.get("provider", "enterprise-sso")},
        )

    user_id = str(user["_id"])
    role = user.get("role", "enterprise")

    if reviewer_auth_service.mfa_enrollment_required(user):
        pending = create_mfa_pending_token(user_id, role, "setup")
        return MfaPendingLoginResponse(
            status="mfa_setup_required",
            mfa_pending_token=pending,
            expires_in=settings.MFA_PENDING_TOKEN_MINUTES * 60,
            user=_build_auth_user(user),
        )

    if user.get("mfa_enabled"):
        pending = create_mfa_pending_token(user_id, role, "verify")
        return MfaPendingLoginResponse(
            status="mfa_required",
            mfa_pending_token=pending,
            expires_in=settings.MFA_PENDING_TOKEN_MINUTES * 60,
            user=_build_auth_user(user),
        )

    return await issue_full_login_response(
        user,
        ip_address,
        user_agent,
        auth_method="password",
        amr=["pwd"],
    )


async def oauth_primary_auth_result(
    user: dict,
    ip_address: Optional[str],
    user_agent: Optional[str],
    *,
    oauth_provider: str = "oauth",
) -> Union[LoginResponse, MfaPendingLoginResponse]:
    """
    MFA branching after Google/Microsoft (or other) OAuth identity is resolved.
    Call this from the OAuth callback once the user document is loaded or created.
    """
    user_id = str(user["_id"])
    role = user.get("role", "enterprise")

    if reviewer_auth_service.mfa_enrollment_required(user):
        pending = create_mfa_pending_token(user_id, role, "setup")
        return MfaPendingLoginResponse(
            status="mfa_setup_required",
            mfa_pending_token=pending,
            expires_in=settings.MFA_PENDING_TOKEN_MINUTES * 60,
            user=_build_auth_user(user),
        )

    if user.get("mfa_enabled"):
        pending = create_mfa_pending_token(user_id, role, "verify")
        return MfaPendingLoginResponse(
            status="mfa_required",
            mfa_pending_token=pending,
            expires_in=settings.MFA_PENDING_TOKEN_MINUTES * 60,
            user=_build_auth_user(user),
        )

    return await issue_full_login_response(
        user,
        ip_address,
        user_agent,
        auth_method=oauth_provider,
        amr=["oauth"],
    )


# ── Validate credentials ──────────────────────────────────────────────────────

async def validate_credentials(payload: LoginRequest) -> ValidateResponse:
    col = get_users_collection()
    user = await col.find_one({"email": payload.email.lower()})

    if not user or not user.get("hashed_password"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NO_ACCOUNT", "message": "We couldn't find an account associated with this email."},
        )

    if not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "WRONG_PASSWORD", "message": "The password you entered is incorrect."},
        )

    return ValidateResponse(valid=True)


# ── Refresh session ───────────────────────────────────────────────────────────

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
    user = await users_col.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.get("mfa_enabled") and payload.get("mfa_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "MFA_SESSION_EXPIRED", "message": "Sign in again to continue."},
        )
    if reviewer_auth_service.mfa_enrollment_required(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "MFA_SETUP_REQUIRED", "message": "Complete MFA enrollment."},
        )

    mfa_ok = payload.get("mfa_verified", True)
    access_token = create_access_token(
        {"sub": payload["sub"], "role": payload.get("role")},
        mfa_verified=bool(mfa_ok),
    )
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


# ── Logout ────────────────────────────────────────────────────────────────────

async def logout_session(refresh_token: str) -> None:
    sessions_col = get_sessions_collection()
    await sessions_col.update_one(
        {"refresh_token_hash": _hash_token(refresh_token)},
        {"$set": {"revoked_at": datetime.now(timezone.utc)}},
    )


async def logout_all_sessions(user_id: str) -> None:
    sessions_col = get_sessions_collection()
    await sessions_col.update_many(
        {"user_id": user_id, "revoked_at": None},
        {"$set": {"revoked_at": datetime.now(timezone.utc)}},
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

    await sessions_col.update_one({"_id": oid}, {"$set": {"revoked_at": datetime.now(timezone.utc)}})


# ── List sessions ─────────────────────────────────────────────────────────────

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

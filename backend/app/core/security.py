from datetime import datetime, timedelta, timezone
from typing import List, Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.database import get_users_collection

http_bearer = HTTPBearer()


# ── Password helpers ──────────────────────────────────────────────────────────

def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))


# ── Token creation ────────────────────────────────────────────────────────────

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    *,
    mfa_verified: bool = True,
    amr: Optional[List[str]] = None,
) -> str:
    to_encode = data.copy()
    to_encode["mfa_verified"] = mfa_verified
    if amr is not None:
        to_encode["amr"] = amr
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    data: dict,
    *,
    mfa_verified: bool = True,
) -> str:
    to_encode = data.copy()
    to_encode["mfa_verified"] = mfa_verified
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_mfa_pending_token(sub: str, role: str, mfa_flow: str) -> str:
    """Short-lived JWT for MFA setup or TOTP verification step."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.MFA_PENDING_TOKEN_MINUTES)
    payload = {
        "sub": sub,
        "role": role,
        "type": "mfa_pending",
        "mfa_flow": mfa_flow,
        "mfa_verified": False,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── Dependencies ─────────────────────────────────────────────────────────────

async def _load_user_by_id(user_id: str) -> Optional[dict]:
    from bson import ObjectId

    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    col = get_users_collection()
    user = await col.find_one({"_id": oid})
    if user is None:
        return None
    user["id"] = str(user["_id"])
    return user


def _enforce_access_mfa_policy(user: dict, payload: dict) -> None:
    """Ensure JWT matches user's MFA state for protected API access."""
    mfa_verified_claim = payload.get("mfa_verified")
    role = str(user.get("role") or "").strip().lower()

    if user.get("mfa_enabled") and mfa_verified_claim is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "MFA_REQUIRED", "message": "Multi-factor authentication required."},
        )

    if role in {"enterprise", "reviewer"} and not user.get("mfa_enabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "MFA_SETUP_REQUIRED", "message": "Complete MFA enrollment to continue."},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    """Full session: access token only, MFA policy enforced for wizard and protected routes."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise credentials_exception
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = await _load_user_by_id(user_id)
    if user is None:
        raise credentials_exception

    _enforce_access_mfa_policy(user, payload)
    return user


async def get_current_user_for_me(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    """Allows access or mfa_pending tokens for /auth/me style bootstrap."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(credentials.credentials)
    typ = payload.get("type")
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = await _load_user_by_id(user_id)
    if user is None:
        raise credentials_exception

    if typ == "mfa_pending":
        user["_auth_token_type"] = "mfa_pending"
        user["_mfa_flow"] = payload.get("mfa_flow")
        return user

    if typ == "access":
        user["_auth_token_type"] = "access"
        _enforce_access_mfa_policy(user, payload)
        return user

    raise credentials_exception


async def get_mfa_pending_principal(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    """Bearer must be mfa_pending JWT (verify / recovery endpoints)."""
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "mfa_pending":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "MFA_SESSION_EXPIRED", "message": "Sign in again to continue."},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = await _load_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return {
        "user": user,
        "payload": payload,
        "mfa_flow": payload.get("mfa_flow"),
        "token_type": "mfa_pending",
    }


async def get_mfa_setup_principal(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    """Bearer: mfa_pending (flow=setup) or access token (contributor enabling MFA)."""
    payload = decode_token(credentials.credentials)
    typ = payload.get("type")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = await _load_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if typ == "mfa_pending":
        if payload.get("mfa_flow") != "setup":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "WRONG_MFA_PHASE", "message": "Use the MFA verification endpoint."},
            )
        return {"user": user, "payload": payload, "token_type": "mfa_pending", "mfa_flow": "setup"}

    if typ == "access":
        if payload.get("mfa_verified") is not True:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return {"user": user, "payload": payload, "token_type": "access", "mfa_flow": None}

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_user_mfa_settings(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    """Full access token for MFA status / disable (settings)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access" or payload.get("mfa_verified") is not True:
        raise credentials_exception
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception
    user = await _load_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    _enforce_access_mfa_policy(user, payload)
    return user

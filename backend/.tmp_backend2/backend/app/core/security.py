from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from bson.errors import InvalidId

from app.core.config import settings
from app.core.database import get_users_collection

http_bearer = HTTPBearer()


def normalize_bearer_token(raw: str) -> str:
    """Strip noise from Swagger / copy-paste (newlines, quotes, duplicate ``Bearer``)."""
    if not raw:
        return ""
    t = raw.strip().replace("\r", "").replace("\n", "").replace("\ufeff", "")
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        t = t[1:-1].strip()
    return t


def _token_shape_error(token: str) -> Optional[str]:
    """Human hint when the value clearly is not a raw JWT."""
    if not token:
        return "Authorization token is empty. In Swagger: Authorize → paste access_token from login."
    if token.strip().startswith("{"):
        return (
            "Value looks like JSON. Paste only the access_token string (the long eyJ... value), "
            "not the whole response body."
        )
    if token.count(".") != 2:
        return (
            "A JWT has exactly two dots (three parts). Copy may be truncated, or this is not access_token. "
            "Re-copy access_token from POST /auth/login (or /auth/mfa/verify) on this same server."
        )
    return None


# ── Password helpers ──────────────────────────────────────────────────────────

def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))


# ── Token creation ────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.signing_algorithm)


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    if expires_delta is not None:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.signing_algorithm)


def decode_token(token: str) -> dict:
    _bearer = {"WWW-Authenticate": "Bearer"}
    hint = _token_shape_error(token)
    if hint:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=hint,
            headers=_bearer,
        )
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.signing_algorithm])
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired. Log in again.",
            headers=_bearer,
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "JWT signature invalid for this server. Log in again at the same base URL as this docs page "
                "(e.g. if docs are http://127.0.0.1:8000, login must be there too). "
                "If you changed SECRET_KEY in .env, old tokens no longer work."
            ),
            headers=_bearer,
        ) from exc


# ── Dependency: resolve current user from Bearer token ───────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    _bearer = {"WWW-Authenticate": "Bearer"}
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers=_bearer,
    )
    token = normalize_bearer_token(credentials.credentials)
    payload = decode_token(token)
    if payload.get("type") != "access":
        if payload.get("type") == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Use access_token in Authorization, not refresh_token.",
                headers=_bearer,
            )
        raise credentials_exception
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    col = get_users_collection()
    from bson import ObjectId

    try:
        oid = ObjectId(user_id)
    except InvalidId:
        raise credentials_exception

    user = await col.find_one({"_id": oid})
    if user is None:
        raise credentials_exception
    if user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "AUTH-008",
                "message": "Your account has been deactivated. Please contact GlimmoraTeam support.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    user["id"] = str(user["_id"])
    return user
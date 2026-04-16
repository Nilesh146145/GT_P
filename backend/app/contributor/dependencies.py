"""
Contributor authorization — aligned with enterprise pattern:

- Production: ``Authorization: Bearer <access_token>`` from ``POST /api/v1/auth/login`` (or OAuth → same tokens).
- MFA: enforced via ``app.core.security._enforce_access_mfa_policy`` (same as wizard / enterprise APIs).
- Dev only: if ``AUTH_ALLOW_HEADER_FALLBACK=true``, ``X-Contributor-Id`` is accepted when no Bearer token is sent.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.security import (
    _enforce_access_mfa_policy,
    _load_user_by_id,
    decode_token,
    get_current_user,
)

http_bearer_optional = HTTPBearer(auto_error=False)


def _contributor_forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "CONTRIBUTOR_REQUIRED",
            "message": "This resource is available to contributor accounts only.",
        },
    )


async def require_contributor_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Same gate as enterprise ``require_enterprise_user``: JWT session + Mongo user, then role check.
    Use this when you want the full ``user`` document in handlers.
    """
    role = str(current_user.get("role") or "").strip().lower()
    if role != "contributor":
        raise _contributor_forbidden()
    return current_user


async def get_contributor_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer_optional)],
    x_contributor_id: Annotated[str | None, Header(alias="X-Contributor-Id")] = None,
) -> str:
    """
    Contributor user id for ``/api/contributor/*``.

    Preferred: Bearer access token (same tokens as enterprise after login / MFA / OAuth).
    Dev fallback: ``X-Contributor-Id`` when ``AUTH_ALLOW_HEADER_FALLBACK`` is true.
    """
    token = credentials.credentials.strip() if credentials and credentials.credentials else None
    if token:
        payload = decode_token(token)
        if payload.get("type") != "access":
            if payload.get("type") == "refresh":
                detail = "Use access_token in Authorization, not refresh_token."
            else:
                detail = "Invalid or non-access token."
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=detail,
                headers={"WWW-Authenticate": "Bearer"},
            )
        uid = payload.get("sub")
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = await _load_user_by_id(str(uid))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        _enforce_access_mfa_policy(user, payload)
        role = str(user.get("role") or "").strip().lower()
        if role != "contributor":
            raise _contributor_forbidden()
        return str(user["id"])

    if settings.AUTH_ALLOW_HEADER_FALLBACK:
        if x_contributor_id and x_contributor_id.strip():
            return x_contributor_id.strip()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials: send Authorization Bearer token or X-Contributor-Id (dev fallback).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


__all__ = [
    "get_contributor_id",
    "http_bearer_optional",
    "require_contributor_user",
]

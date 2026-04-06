"""
Google / Microsoft OAuth: authorize redirects, token exchange, user linking, MFA branch.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional, Union
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import settings
from app.core.database import get_users_collection
from app.schemas.auth import LoginResponse, MfaPendingLoginResponse
from app.services import auth_service

logger = logging.getLogger(__name__)

OAuthProvider = Literal["google", "microsoft"]


def new_pkce_verifier() -> str:
    """RFC 7636: 43–128 characters."""
    return secrets.token_urlsafe(48)


def pkce_challenge_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_oauth_state(provider: OAuthProvider, *, code_verifier: Optional[str] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload: dict = {"typ": "oauth_state", "provider": provider, "exp": expire}
    if code_verifier:
        payload["cv"] = code_verifier
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_oauth_state(state: str, expect: OAuthProvider) -> Optional[str]:
    """Validate state JWT; return PKCE code_verifier if present."""
    try:
        data = jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "OAUTH_INVALID_STATE", "message": "Invalid or expired OAuth state. Start sign-in again."},
        ) from exc
    if data.get("typ") != "oauth_state":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")
    p = data.get("provider")
    if p != expect:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")
    cv = data.get("cv")
    return str(cv) if cv else None


def callback_path(provider: OAuthProvider) -> str:
    return f"/api/v1/auth/oauth/{provider}/callback"


def build_redirect_uri(request: Request, provider: OAuthProvider) -> str:
    """Absolute callback URL as seen by the browser (must match IdP app registration)."""
    if settings.OAUTH_PUBLIC_BASE_URL:
        base = settings.OAUTH_PUBLIC_BASE_URL.rstrip("/")
        return f"{base}/api/v1/auth/oauth/{provider}/callback"
    u = urlparse(str(request.base_url))
    scheme = u.scheme or "http"
    host = u.netloc or request.headers.get("host", "127.0.0.1:8000")
    return f"{scheme}://{host}{callback_path(provider)}"


def google_authorize_url(redirect_uri: str, state: str, *, code_challenge: str) -> str:
    if not settings.google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "OAUTH_NOT_CONFIGURED",
                "message": "Google OAuth is not configured. Set non-empty GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in the "
                ".env file at the project root (same folder as app/). Remove empty GOOGLE_CLIENT_ID= lines. Restart uvicorn.",
            },
        )
    # PKCE (S256) avoids "Access blocked / request is invalid" for many Google OAuth web clients.
    q = urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{q}"


def microsoft_authorize_url(redirect_uri: str, state: str, *, code_challenge: str) -> str:
    if not settings.microsoft_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "OAUTH_NOT_CONFIGURED",
                "message": "Microsoft OAuth is not configured. Set non-empty MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET in .env.",
            },
        )
    tenant = settings.MICROSOFT_TENANT_ID or "common"
    q = urlencode(
        {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "response_type": "code",
            "scope": "openid email profile User.Read",
            "redirect_uri": redirect_uri,
            "state": state,
            "response_mode": "query",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{q}"


async def _exchange_google_code(
    code: str,
    redirect_uri: str,
    *,
    code_verifier: Optional[str] = None,
) -> dict:
    form = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if code_verifier:
        form["code_verifier"] = code_verifier
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            "https://oauth2.googleapis.com/token",
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if r.status_code != 200:
        logger.warning("Google token exchange failed: %s %s", r.status_code, r.text[:200])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "OAUTH_TOKEN_EXCHANGE_FAILED", "message": "Could not complete Google sign-in."},
        )
    return r.json()


async def _google_userinfo(access_token: str) -> tuple[str, str, str]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not read Google profile.")
    data = r.json()
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account has no email.")
    given = data.get("given_name") or ""
    family = data.get("family_name") or ""
    return email, given, family


async def _exchange_microsoft_code(
    code: str,
    redirect_uri: str,
    *,
    code_verifier: Optional[str] = None,
) -> dict:
    tenant = settings.MICROSOFT_TENANT_ID or "common"
    form = {
        "code": code,
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "client_secret": settings.MICROSOFT_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "scope": "openid email profile User.Read",
    }
    if code_verifier:
        form["code_verifier"] = code_verifier
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if r.status_code != 200:
        logger.warning("Microsoft token exchange failed: %s %s", r.status_code, r.text[:200])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "OAUTH_TOKEN_EXCHANGE_FAILED", "message": "Could not complete Microsoft sign-in."},
        )
    return r.json()


async def _microsoft_userinfo(access_token: str) -> tuple[str, str, str]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not read Microsoft profile.")
    data = r.json()
    email = (data.get("mail") or data.get("userPrincipalName") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Microsoft account has no usable email.")
    given = data.get("givenName") or ""
    family = data.get("surname") or ""
    return email, given, family


async def find_or_create_oauth_user(
    email: str,
    first_name: str,
    last_name: str,
    provider: OAuthProvider,
) -> dict:
    col = get_users_collection()
    user = await col.find_one({"email": email})
    now = datetime.now(timezone.utc)

    if user:
        await col.update_one(
            {"_id": user["_id"]},
            {"$set": {"updated_at": now, "last_oauth_provider": provider}},
        )
        user = await col.find_one({"_id": user["_id"]})
    else:
        full_name = f"{first_name} {last_name}".strip() or email.split("@")[0]
        doc = {
            "email": email,
            "hashed_password": None,
            "first_name": first_name or email.split("@")[0],
            "last_name": last_name or "",
            "full_name": full_name,
            "role": "contributor",
            "provider": provider,
            "mfa_enabled": False,
            "email_verified": True,
            "phone_verified": False,
            "sso_only": True,
            "created_at": now,
            "updated_at": now,
        }
        ins = await col.insert_one(doc)
        user = await col.find_one({"_id": ins.inserted_id})

    if user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User persistence failed.")
    user["id"] = str(user["_id"])
    return user


async def complete_google_login(
    code: str,
    state: str,
    redirect_uri: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> Union[LoginResponse, MfaPendingLoginResponse]:
    cv = decode_oauth_state(state, "google")
    tokens = await _exchange_google_code(code, redirect_uri, code_verifier=cv)
    access = tokens.get("access_token")
    if not access:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No access token from Google.")
    email, given, family = await _google_userinfo(access)
    user = await find_or_create_oauth_user(email, given, family, "google")
    return await auth_service.oauth_primary_auth_result(
        user,
        ip_address,
        user_agent,
        oauth_provider="google_oauth",
    )


async def complete_microsoft_login(
    code: str,
    state: str,
    redirect_uri: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> Union[LoginResponse, MfaPendingLoginResponse]:
    cv = decode_oauth_state(state, "microsoft")
    tokens = await _exchange_microsoft_code(code, redirect_uri, code_verifier=cv)
    access = tokens.get("access_token")
    if not access:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No access token from Microsoft.")
    email, given, family = await _microsoft_userinfo(access)
    user = await find_or_create_oauth_user(email, given, family, "microsoft")
    return await auth_service.oauth_primary_auth_result(
        user,
        ip_address,
        user_agent,
        oauth_provider="microsoft_oauth",
    )

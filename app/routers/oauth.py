"""
OAuth — Google and Microsoft sign-in with the same MFA branching as password login.

  GET /auth/oauth/google/authorize     → redirect to Google
  GET /auth/oauth/google/callback      → JSON: LoginResponse | MfaPendingLoginResponse
  GET /auth/oauth/microsoft/authorize  → redirect to Microsoft
  GET /auth/oauth/microsoft/callback   → JSON: LoginResponse | MfaPendingLoginResponse

Register the exact callback URLs in Google Cloud Console and Azure App Registration.
"""

from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.schemas.auth import LoginResponse, MfaPendingLoginResponse
from app.services import oauth_service

router = APIRouter(prefix="/auth/oauth", tags=["OAuth"])


@router.get(
    "/google/diagnostic",
    summary="Dev: exact redirect_uri + config hints (fix Google Console mismatch)",
)
async def google_oauth_diagnostic(request: Request) -> dict:
    rid = oauth_service.build_redirect_uri(request, "google")
    return {
        "google_oauth_configured": settings.google_oauth_configured(),
        "redirect_uri_register_this_exactly_in_google_console": rid,
        "request_base_url": str(request.base_url),
        "oauth_public_base_url": settings.OAUTH_PUBLIC_BASE_URL,
        "pkce": "enabled (S256); state JWT carries code_verifier for token exchange",
        "tips": [
            "Authorized redirect URIs in Google must match redirect_uri above character-for-character.",
            "Open /authorize with the same host you registered (127.0.0.1 vs localhost are different).",
            "If using a reverse proxy / https public URL, set OAUTH_PUBLIC_BASE_URL and register that https callback.",
            "OAuth consent screen: if Testing, add your Google account under Test users.",
        ],
    }


@router.get(
    "/microsoft/diagnostic",
    summary="Dev: exact redirect_uri + config hints (fix Azure App Registration mismatch)",
)
async def microsoft_oauth_diagnostic(request: Request) -> dict:
    rid = oauth_service.build_redirect_uri(request, "microsoft")
    return {
        "microsoft_oauth_configured": settings.microsoft_oauth_configured(),
        "redirect_uri_register_this_exactly_in_azure": rid,
        "microsoft_tenant_id": settings.MICROSOFT_TENANT_ID,
        "request_base_url": str(request.base_url),
        "oauth_public_base_url": settings.OAUTH_PUBLIC_BASE_URL,
        "pkce": "enabled (S256); state JWT carries code_verifier for token exchange",
        "tips": [
            "Azure AD: App registration → Authentication → add a Web platform redirect URI matching the value above exactly.",
            "Use the same host to open /authorize as in redirect_uri (127.0.0.1 vs localhost differ).",
            "Delegated Graph permissions: openid, email, profile, User.Read (admin consent if required by tenant).",
            "MICROSOFT_TENANT_ID=common allows personal Microsoft accounts; use your tenant GUID for single-tenant only.",
            "If behind a proxy / public https URL, set OAUTH_PUBLIC_BASE_URL and register that https callback.",
        ],
    }


def _client_meta(request: Request) -> tuple[Optional[str], Optional[str]]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


@router.get("/google/authorize", summary="Start Google sign-in (browser redirect)")
async def google_authorize(request: Request) -> RedirectResponse:
    redirect_uri = oauth_service.build_redirect_uri(request, "google")
    verifier = oauth_service.new_pkce_verifier()
    challenge = oauth_service.pkce_challenge_s256(verifier)
    state = oauth_service.create_oauth_state("google", code_verifier=verifier)
    url = oauth_service.google_authorize_url(redirect_uri, state, code_challenge=challenge)
    return RedirectResponse(url=url, status_code=302)


@router.get(
    "/google/callback",
    response_model=Union[LoginResponse, MfaPendingLoginResponse],
    summary="Google OAuth callback (returns JSON for SPA/dev)",
)
async def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
) -> Union[LoginResponse, MfaPendingLoginResponse]:
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "OAUTH_DENIED",
                "message": error_description or error,
            },
        )
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "OAUTH_MISSING_PARAMS", "message": "Missing authorization code or state."},
        )
    redirect_uri = oauth_service.build_redirect_uri(request, "google")
    ip, ua = _client_meta(request)
    return await oauth_service.complete_google_login(code, state, redirect_uri, ip, ua)


@router.get("/microsoft/authorize", summary="Start Microsoft sign-in (browser redirect)")
async def microsoft_authorize(request: Request) -> RedirectResponse:
    redirect_uri = oauth_service.build_redirect_uri(request, "microsoft")
    verifier = oauth_service.new_pkce_verifier()
    challenge = oauth_service.pkce_challenge_s256(verifier)
    state = oauth_service.create_oauth_state("microsoft", code_verifier=verifier)
    url = oauth_service.microsoft_authorize_url(redirect_uri, state, code_challenge=challenge)
    return RedirectResponse(url=url, status_code=302)


@router.get(
    "/microsoft/callback",
    response_model=Union[LoginResponse, MfaPendingLoginResponse],
    summary="Microsoft OAuth callback (returns JSON for SPA/dev)",
)
async def microsoft_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
) -> Union[LoginResponse, MfaPendingLoginResponse]:
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "OAUTH_DENIED",
                "message": error_description or error,
            },
        )
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "OAUTH_MISSING_PARAMS", "message": "Missing authorization code or state."},
        )
    redirect_uri = oauth_service.build_redirect_uri(request, "microsoft")
    ip, ua = _client_meta(request)
    return await oauth_service.complete_microsoft_login(code, state, redirect_uri, ip, ua)

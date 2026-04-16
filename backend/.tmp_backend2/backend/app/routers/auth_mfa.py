"""
MFA routes under ``/api/v1/auth/mfa/*`` (aligned with deployed OpenAPI).

Swagger lists the six public MFA operations; ``setup/cancel`` and ``recovery-codes`` stay
callable but are hidden from ``/docs`` (same pattern as production).
"""

from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Request

from app.core.security import get_current_user
from app.schemas.auth import (
    LoginResponse,
    LogoutResponse,
    MfaEnrollmentCompleteResponse,
    MfaLoginRecoveryRequest,
    MfaLoginTotpRequest,
    MfaPasswordTotpRequest,
    MfaSetupResponse,
    MfaStatusResponse,
    MfaVerifySetupRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/mfa", tags=["MFA"])


def _client_meta(request: Request) -> Tuple[Optional[str], Optional[str]]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


@router.post(
    "/setup/init",
    response_model=MfaSetupResponse,
    summary="Start TOTP enrollment",
)
async def mfa_setup_init(current_user: dict = Depends(get_current_user)) -> MfaSetupResponse:
    """Returns secret + ``otpauth://`` URI. Complete with ``POST /auth/mfa/setup/confirm``."""
    return await auth_service.start_mfa_setup(current_user["id"], current_user["email"])


@router.post(
    "/setup/confirm",
    response_model=MfaEnrollmentCompleteResponse,
    summary="Confirm TOTP enrollment",
)
async def mfa_setup_confirm(
    payload: MfaVerifySetupRequest,
    current_user: dict = Depends(get_current_user),
) -> MfaEnrollmentCompleteResponse:
    """Verify TOTP against the pending secret; enables MFA and returns one-time recovery codes."""
    codes = await auth_service.verify_mfa_setup(current_user["id"], payload.code)
    return MfaEnrollmentCompleteResponse(recovery_codes=codes)


@router.post(
    "/setup/cancel",
    response_model=LogoutResponse,
    summary="Cancel pending TOTP setup",
    include_in_schema=False,
)
async def mfa_setup_cancel(current_user: dict = Depends(get_current_user)) -> LogoutResponse:
    """Abandon enrollment before ``setup/confirm`` (clears temporary secret)."""
    await auth_service.cancel_mfa_setup(current_user["id"])
    return LogoutResponse(success=True)


@router.post(
    "/verify",
    response_model=LoginResponse,
    summary="Complete login with TOTP",
)
async def mfa_verify_login_totp(
    payload: MfaLoginTotpRequest,
    request: Request,
) -> LoginResponse:
    """After ``POST /auth/login`` returned ``mfa_required``, submit email + TOTP for tokens."""
    ip_address, user_agent = _client_meta(request)
    return await auth_service.verify_login_mfa(
        email=payload.email,
        code=payload.code,
        recovery_code=None,
        remember_me=payload.remember_me,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/recovery",
    response_model=LoginResponse,
    summary="Complete login with recovery code",
)
async def mfa_verify_login_recovery(
    payload: MfaLoginRecoveryRequest,
    request: Request,
) -> LoginResponse:
    """After ``mfa_required``, submit email + one-time recovery code for tokens."""
    ip_address, user_agent = _client_meta(request)
    return await auth_service.verify_login_mfa(
        email=payload.email,
        code=None,
        recovery_code=payload.recovery_code,
        remember_me=payload.remember_me,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/disable",
    response_model=LogoutResponse,
    summary="Disable MFA (contributors only)",
)
async def mfa_disable(
    payload: MfaPasswordTotpRequest,
    current_user: dict = Depends(get_current_user),
) -> LogoutResponse:
    """
    Disable TOTP MFA (password + current TOTP). Reviewer accounts receive 403.

    Revokes all sessions.
    """
    await auth_service.disable_mfa(current_user["id"], payload.password, payload.code)
    return LogoutResponse(success=True)


@router.get(
    "/status",
    response_model=MfaStatusResponse,
    summary="MFA enrollment status",
)
async def mfa_status(current_user: dict = Depends(get_current_user)) -> MfaStatusResponse:
    """Whether MFA is enabled, pending enrollment, and remaining recovery codes."""
    return await auth_service.get_mfa_status(current_user["id"])


@router.post(
    "/recovery-codes",
    response_model=MfaEnrollmentCompleteResponse,
    summary="Regenerate MFA recovery codes",
    include_in_schema=False,
)
async def mfa_regenerate_recovery_codes(
    payload: MfaPasswordTotpRequest,
    current_user: dict = Depends(get_current_user),
) -> MfaEnrollmentCompleteResponse:
    """Rotate recovery codes; old codes stop working immediately."""
    codes = await auth_service.regenerate_mfa_recovery_codes(
        current_user["id"], payload.password, payload.code
    )
    return MfaEnrollmentCompleteResponse(
        recovery_codes=codes,
        message="Previous recovery codes are no longer valid. Store these new codes securely.",
    )

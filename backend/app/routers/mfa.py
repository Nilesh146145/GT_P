"""
MFA Router — RFC 6238 TOTP (Google Authenticator / Microsoft Authenticator).

  POST /auth/mfa/setup/init
  POST /auth/mfa/setup/confirm
  POST /auth/mfa/verify
  POST /auth/mfa/recovery
  POST /auth/mfa/disable
  GET  /auth/mfa/status
"""
from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.security import (
    get_current_user_mfa_settings,
    get_mfa_pending_principal,
    get_mfa_setup_principal,
)
from app.schemas.auth import LoginResponse
from app.schemas.mfa import (
    MfaDisableRequest,
    MfaDisableResponse,
    MfaRecoveryRequest,
    MfaSetupConfirmResponse,
    MfaSetupInitResponse,
    MfaStatusResponse,
    MfaTotpCodeRequest,
)
from app.services import auth_service, mfa_service

router = APIRouter(prefix="/auth/mfa", tags=["MFA"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


@router.post("/setup/init", response_model=MfaSetupInitResponse, summary="Start TOTP enrollment")
async def mfa_setup_init(
    request: Request,
    principal: dict = Depends(get_mfa_setup_principal),
) -> MfaSetupInitResponse:
    """Requires mfa_pending (enterprise first login) or full access token (contributor enabling MFA)."""
    ip, ua = _client_meta(request)
    user = principal["user"]
    otpauth_uri, secret = await mfa_service.init_setup(user, ip_address=ip, user_agent=ua)
    return MfaSetupInitResponse(otpauth_uri=otpauth_uri, secret_base32=secret)


@router.post("/setup/confirm", response_model=MfaSetupConfirmResponse, summary="Confirm TOTP enrollment")
async def mfa_setup_confirm(
    body: MfaTotpCodeRequest,
    request: Request,
    principal: dict = Depends(get_mfa_setup_principal),
) -> MfaSetupConfirmResponse:
    ip, ua = _client_meta(request)
    user = principal["user"]
    recovery_codes = await mfa_service.confirm_setup(
        user, body.code, ip_address=ip, user_agent=ua
    )
    refreshed = await mfa_service.load_user_by_id(user["id"])
    if not refreshed:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User load failed")
    login = await auth_service.issue_full_login_response(
        refreshed,
        ip_address=ip,
        user_agent=ua,
        auth_method="mfa_enrollment",
        amr=["otp"],
    )
    return MfaSetupConfirmResponse(
        recovery_codes=recovery_codes,
        access_token=login.access_token,
        refresh_token=login.refresh_token,
        expires_in=login.expires_in,
        user=login.user,
    )


@router.post("/verify", response_model=LoginResponse, summary="Complete login with TOTP")
async def mfa_verify(
    body: MfaTotpCodeRequest,
    request: Request,
    principal: dict = Depends(get_mfa_pending_principal),
) -> LoginResponse:
    if principal.get("mfa_flow") != "verify":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WRONG_MFA_PHASE", "message": "Use setup endpoints to enroll MFA."},
        )
    ip, ua = _client_meta(request)
    uid = principal["user"]["id"]
    await mfa_service.verify_totp_code(uid, body.code, ip_address=ip, user_agent=ua)
    user = await mfa_service.load_user_by_id(uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User load failed")
    return await auth_service.issue_full_login_response(
        user,
        ip_address=ip,
        user_agent=ua,
        auth_method="totp",
        amr=["pwd", "mfa"],
    )


@router.post("/recovery", response_model=LoginResponse, summary="Complete login with recovery code")
async def mfa_recovery(
    body: MfaRecoveryRequest,
    request: Request,
    principal: dict = Depends(get_mfa_pending_principal),
) -> LoginResponse:
    if principal.get("mfa_flow") != "verify":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WRONG_MFA_PHASE", "message": "Recovery is only valid after password or SSO sign-in."},
        )
    ip, ua = _client_meta(request)
    uid = principal["user"]["id"]
    await mfa_service.consume_recovery_code(
        uid, body.recovery_code, ip_address=ip, user_agent=ua
    )
    user = await mfa_service.load_user_by_id(uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User load failed")
    return await auth_service.issue_full_login_response(
        user,
        ip_address=ip,
        user_agent=ua,
        auth_method="recovery_code",
        amr=["pwd", "recovery"],
    )


@router.post("/disable", response_model=MfaDisableResponse, summary="Disable MFA (contributors only)")
async def mfa_disable(
    body: MfaDisableRequest,
    request: Request,
    current_user: dict = Depends(get_current_user_mfa_settings),
) -> MfaDisableResponse:
    ip, ua = _client_meta(request)
    await mfa_service.disable_mfa_for_user(
        current_user, body.password, ip_address=ip, user_agent=ua
    )
    return MfaDisableResponse(success=True)


@router.get(
    "/status",
    response_model=MfaStatusResponse,
    response_model_by_alias=True,
    summary="MFA enrollment status",
)
async def mfa_status(current_user: dict = Depends(get_current_user_mfa_settings)) -> MfaStatusResponse:
    return MfaStatusResponse(
        mfaEnabled=bool(current_user.get("mfa_enabled")),
        mfaEnrollmentRequired=mfa_service.mfa_enrollment_required(current_user),
    )

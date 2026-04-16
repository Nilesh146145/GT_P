"""Contributor settings and account API routes."""

from __future__ import annotations

import urllib.parse

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.contributor.schemas.settings import (
    ChangePasswordBody,
    ContributorSettingsResponse,
    DeactivateAccountBody,
    PatchAccountBody,
    PatchLocaleBody,
    PatchNotificationsBody,
    TwoFactorDisableBody,
    TwoFactorSetupResponse,
    TwoFactorVerifyBody,
)
from app.contributor.dependencies import get_contributor_id
from app.contributor.settings_state import state

router = APIRouter(
    prefix="/api/contributor",
    tags=["contributor"],
    dependencies=[Depends(get_contributor_id)],
)

DEACTIVATE_CONFIRMATION = "DEACTIVATE"


@router.get("/settings", response_model=ContributorSettingsResponse)
def get_settings() -> ContributorSettingsResponse:
    return ContributorSettingsResponse(
        account_summary=state.account_summary,
        notification_preferences=state.notification_preferences,
        language=state.language,
        timezone=state.timezone,
        quiet_hours_start=state.quiet_hours_start,
        quiet_hours_end=state.quiet_hours_end,
        two_factor_enabled=state.two_factor_enabled,
    )


@router.patch("/settings/account", response_model=ContributorSettingsResponse)
def patch_account(body: PatchAccountBody) -> ContributorSettingsResponse:
    data = state.account_summary.model_dump()
    if body.display_name is not None:
        data["display_name"] = body.display_name
    if body.email is not None:
        data["email"] = body.email
    if body.phone is not None:
        data["phone"] = body.phone
    state.account_summary = type(state.account_summary).model_validate(data)
    return get_settings()


@router.patch("/settings/notifications", response_model=ContributorSettingsResponse)
def patch_notifications(body: PatchNotificationsBody) -> ContributorSettingsResponse:
    prefs = state.notification_preferences.model_dump()
    for key in (
        "task_assignments",
        "review_decisions",
        "sla_reminders",
        "payout_updates",
        "learning",
    ):
        val = getattr(body, key)
        if val is not None:
            prefs[key] = val
    state.notification_preferences = type(state.notification_preferences).model_validate(
        prefs
    )
    return get_settings()


@router.patch("/settings/locale", response_model=ContributorSettingsResponse)
def patch_locale(body: PatchLocaleBody) -> ContributorSettingsResponse:
    if body.language is not None:
        state.language = body.language
    if body.timezone is not None:
        state.timezone = body.timezone
    if body.quiet_hours_start is not None:
        state.quiet_hours_start = body.quiet_hours_start
    if body.quiet_hours_end is not None:
        state.quiet_hours_end = body.quiet_hours_end
    return get_settings()


@router.post("/settings/security/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: ChangePasswordBody) -> Response:
    if body.current_password != state._password_plain_demo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    state._password_plain_demo = body.new_password
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _otpauth_uri(secret: str, label: str = "contributor@example.com") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=label,
        issuer_name="Glimmora",
    )


@router.post(
    "/settings/security/2fa/setup",
    response_model=TwoFactorSetupResponse,
)
def two_factor_setup() -> TwoFactorSetupResponse:
    secret = pyotp.random_base32()
    state.pending_totp_secret = secret
    totp = pyotp.TOTP(secret)
    manual_code = totp.secret
    otpauth = _otpauth_uri(secret)
    qr_code_url = (
        "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data="
        + urllib.parse.quote(otpauth, safe="")
    )
    return TwoFactorSetupResponse(
        qr_code_url=qr_code_url,
        secret=secret,
        manual_code=manual_code,
    )


@router.post("/settings/security/2fa/verify", response_model=ContributorSettingsResponse)
def two_factor_verify(body: TwoFactorVerifyBody) -> ContributorSettingsResponse:
    if not state.pending_totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No 2FA setup in progress; call setup first",
        )
    totp = pyotp.TOTP(state.pending_totp_secret)
    if not totp.verify(body.verification_code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )
    state.totp_secret = state.pending_totp_secret
    state.pending_totp_secret = None
    state.two_factor_enabled = True
    return get_settings()


@router.post("/settings/security/2fa/disable", response_model=ContributorSettingsResponse)
def two_factor_disable(body: TwoFactorDisableBody) -> ContributorSettingsResponse:
    if not state.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled",
        )
    if body.password is not None:
        if body.password != state._password_plain_demo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password",
            )
    else:
        assert body.verification_code is not None
        if not state.totp_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="2FA state inconsistent",
            )
        totp = pyotp.TOTP(state.totp_secret)
        if not totp.verify(body.verification_code, valid_window=1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code",
            )
    state.two_factor_enabled = False
    state.totp_secret = None
    state.pending_totp_secret = None
    return get_settings()


@router.post("/account/deactivate", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_account(body: DeactivateAccountBody) -> Response:
    if body.confirmation_text.strip() != DEACTIVATE_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'confirmation_text must be exactly "{DEACTIVATE_CONFIRMATION}"',
        )
    if body.password is not None and body.password != state._password_plain_demo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password",
        )
    # Demo: mark account inactive — replace with DB update / auth revocation
    state.account_summary = type(state.account_summary).model_validate(
        {
            **state.account_summary.model_dump(),
            "display_name": "[deactivated]",
        }
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

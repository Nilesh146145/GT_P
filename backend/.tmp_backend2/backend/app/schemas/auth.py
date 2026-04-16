"""
Auth schemas — derived from app/schemas/auth.py in the reference app.
"""

from datetime import datetime
from typing import List, Literal, Optional, Union
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.auth_fsd import MFA_STEP2_MESSAGE


def _validate_password(v: str) -> str:
    # FSD §3.2.1 / §3.5 — min 12 characters for Enterprise Portal
    if len(v) < 12:
        raise ValueError("Password must be at least 12 characters")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 characters (bcrypt limit)")
    return v


class LoginRequest(BaseModel):
    """
    JSON body for ``POST /auth/login`` (same field names as ``POST /auth/validate``).

    ``remember_me`` / ``rememberMe`` extends refresh-token lifetime when MFA is off.
    """

    email: EmailStr
    password: str
    workspace: Optional[str] = None
    remember_me: bool = Field(
        default=False,
        validation_alias=AliasChoices("remember_me", "rememberMe"),
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "YourPassword12",
                "rememberMe": False,
            }
        },
    )


class AuthUser(BaseModel):
    id: Union[str, UUID]
    email: EmailStr
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    role: str = "enterprise"
    provider: str
    phone_verified: bool = Field(alias="phoneVerified")
    email_verified: bool = Field(alias="emailVerified")
    is_first_login: bool = Field(default=False, alias="isFirstLogin")
    is_mfa_enabled: bool = Field(default=False, alias="isMfaEnabled")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUser


class MfaRequiredLoginResponse(BaseModel):
    """
    FSD §3.3.4 step 2 — password verified; **no** ``access_token`` / ``refresh_token`` yet.

    Client must call ``POST /auth/mfa/verify`` (TOTP) or ``POST /auth/mfa/recovery``
    with ``email`` and the second factor.
    """

    mfa_required: Literal[True] = True
    email: EmailStr
    step: int = 2
    message: str = MFA_STEP2_MESSAGE

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mfa_required": True,
                "email": "user@example.com",
                "step": 2,
                "message": MFA_STEP2_MESSAGE,
            }
        },
    )


class MfaSetupResponse(BaseModel):
    """One-time secret for enrolling an authenticator (store only until verified)."""

    secret: str
    otpauth_url: str


class MfaVerifySetupRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=10)


class MfaVerifyLoginRequest(BaseModel):
    """FSD §3.3.6 — TOTP or single-use recovery code (§3.3.6)."""

    email: EmailStr
    code: Optional[str] = Field(default=None, min_length=6, max_length=10)
    recovery_code: Optional[str] = Field(default=None, min_length=8, max_length=32)
    remember_me: bool = Field(
        default=False,
        validation_alias=AliasChoices("remember_me", "rememberMe"),
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {"email": "user@example.com", "code": "123456", "rememberMe": False},
        },
    )

    @model_validator(mode="after")
    def require_one_second_factor(self):
        has_totp = bool(self.code and self.code.strip())
        has_rec = bool(self.recovery_code and self.recovery_code.strip())
        if not has_totp and not has_rec:
            raise ValueError("Provide either code (TOTP) or recovery_code.")
        if has_totp and has_rec:
            raise ValueError("Provide only one of code or recovery_code.")
        return self


class MfaLoginTotpRequest(BaseModel):
    """Second-factor login with TOTP only (``POST /auth/mfa/verify``)."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=10)
    remember_me: bool = Field(
        default=False,
        validation_alias=AliasChoices("remember_me", "rememberMe"),
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {"email": "user@example.com", "code": "123456", "rememberMe": False},
        },
    )


class MfaLoginRecoveryRequest(BaseModel):
    """Second-factor login with a one-time recovery code (``POST /auth/mfa/recovery``)."""

    email: EmailStr
    recovery_code: str = Field(
        ...,
        min_length=8,
        max_length=32,
        validation_alias=AliasChoices("recovery_code", "recoveryCode"),
    )
    remember_me: bool = Field(
        default=False,
        validation_alias=AliasChoices("remember_me", "rememberMe"),
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "recoveryCode": "ABCD-1234-EFGH",
                "rememberMe": False,
            },
        },
    )


# Legacy combined body (TOTP XOR recovery) — prefer ``MfaLoginTotpRequest`` / ``MfaLoginRecoveryRequest``.
VerifyLoginMfaRequest = MfaVerifyLoginRequest


class MfaEnrollmentCompleteResponse(BaseModel):
    """FSD §3.3.2 — recovery codes shown once after MFA enrollment."""

    success: bool = True
    recovery_codes: List[str]
    message: str = (
        "Store these safely. Each can only be used once. They will not be shown again."
    )


class MfaPasswordTotpRequest(BaseModel):
    """Re-authenticate with password + current TOTP for sensitive MFA actions."""

    password: str = Field(..., min_length=1)
    code: str = Field(..., min_length=6, max_length=10)


class MfaStatusResponse(BaseModel):
    """MFA state for security settings UI."""

    mfa_enabled: bool
    pending_enrollment: bool
    recovery_codes_remaining: int


class MfaRequiredResponse(BaseModel):
    status: str = "mfa_required"
    challenge_id: str
    methods: List[str]


class SsoRequiredResponse(BaseModel):
    status: str = "sso_required"
    provider_hint: Optional[str] = None


class ValidateResponse(BaseModel):
    valid: bool


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutResponse(BaseModel):
    success: bool


class CurrentUserResponse(BaseModel):
    id: str
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    email: EmailStr
    email_verified: bool = Field(alias="emailVerified")
    phone_verified: bool = Field(alias="phoneVerified")
    role: str = "enterprise"
    requires_password_change: bool = Field(default=False, alias="requiresPasswordChange")
    is_first_login: bool = Field(default=False, alias="isFirstLogin")
    is_mfa_enabled: bool = Field(default=False, alias="isMfaEnabled")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SessionItem(BaseModel):
    id: str
    auth_method: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    expires_at: datetime


class SessionListResponse(BaseModel):
    sessions: List[SessionItem]


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    role: Optional[str] = None


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def new_pw_limits(cls, v: str) -> str:
        return _validate_password(v)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def new_pw_limits(cls, v: str) -> str:
        return _validate_password(v)



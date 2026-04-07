"""
Auth schemas — derived from app/schemas/auth.py in the reference app.
"""

from datetime import datetime
from typing import List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validate_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 characters (bcrypt limit)")
    return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    workspace: Optional[str] = Field(
        default=None,
        description="Optional. Omit or use null — not required for login or MFA testing.",
    )


class AuthUser(BaseModel):
    id: Union[str, UUID]
    email: EmailStr
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    role: str
    provider: str
    phone_verified: bool = Field(alias="phoneVerified")
    email_verified: bool = Field(alias="emailVerified")
    requires_password_change: bool = Field(default=False, alias="requiresPasswordChange")
    is_first_login: bool = Field(default=False, alias="isFirstLogin")
    mfa_enabled: bool = Field(default=False, alias="mfaEnabled")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user: AuthUser


class MfaPendingLoginResponse(BaseModel):
    """Returned when primary auth succeeded but MFA setup or verification is required."""

    status: Literal["mfa_required", "mfa_setup_required"]
    mfa_pending_token: str
    expires_in: int
    user: AuthUser
    methods: List[str] = Field(default_factory=lambda: ["totp", "recovery_code"])


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
    role: str = "contributor"
    requires_password_change: bool = Field(default=False, alias="requiresPasswordChange")
    is_first_login: bool = Field(default=False, alias="isFirstLogin")
    mfa_enabled: bool = Field(default=False, alias="mfaEnabled")
    mfa_enrollment_required: bool = Field(default=False, alias="mfaEnrollmentRequired")
    auth_pending: bool = Field(default=False, alias="authPending")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        ser_json_by_alias=True,
    )


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


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def new_password_limits(cls, value: str) -> str:
        return _validate_password(value)

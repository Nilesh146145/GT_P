"""
MFA API schemas — TOTP setup, verify, recovery, status.
"""
from __future__ import annotations


from typing import List

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import AuthUser


class MfaTotpCodeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=12)


class MfaRecoveryRequest(BaseModel):
    recovery_code: str = Field(..., min_length=8, max_length=128)


class MfaDisableRequest(BaseModel):
    password: str = Field(..., min_length=1)


class MfaSetupInitResponse(BaseModel):
    otpauth_uri: str
    secret_base32: str


class MfaSetupConfirmResponse(BaseModel):
    recovery_codes: List[str]
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user: AuthUser


class MfaStatusResponse(BaseModel):
    mfa_enabled: bool = Field(alias="mfaEnabled")
    mfa_enrollment_required: bool = Field(alias="mfaEnrollmentRequired")

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)


class MfaDisableResponse(BaseModel):
    success: bool = True

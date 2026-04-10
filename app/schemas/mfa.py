"""
MFA API schemas — TOTP setup, verify, recovery, status.
"""

from typing import Any, List

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from app.schemas.auth import AuthUser


class MfaTotpCodeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=12)


class MfaRecoveryRequest(BaseModel):
    recovery_code: str = Field(..., min_length=8, max_length=128)


class MfaDisableRequest(BaseModel):
    password: str = Field(..., min_length=1)


class MfaSetupInitResponse(BaseModel):
    """
    TOTP enrollment payload. JSON includes both snake_case and camelCase keys so
    Next.js/TS clients using otpAuthUri / secretBase32 receive data without mapping.
    """

    otpauth_uri: str = Field(..., description="otpauth:// provisioning URI for authenticator apps")
    secret_base32: str = Field(..., description="Base32 secret for manual entry")
    qr_code_png_base64: str | None = Field(
        default=None,
        description="PNG of the QR code, raw base64 (prefix with data:image/png;base64, for img src)",
    )

    model_config = ConfigDict(populate_by_name=True)

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "otpauth_uri": self.otpauth_uri,
            "secret_base32": self.secret_base32,
            "otpAuthUri": self.otpauth_uri,
            "secretBase32": self.secret_base32,
        }
        if self.qr_code_png_base64:
            out["qr_code_png_base64"] = self.qr_code_png_base64
            out["qrCodePngBase64"] = self.qr_code_png_base64
        return out


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

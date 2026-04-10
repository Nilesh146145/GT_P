from pydantic import BaseModel, ConfigDict, Field


class ReviewerAuthState(BaseModel):
    role: str
    requires_password_change: bool = Field(default=False, alias="requiresPasswordChange")
    is_first_login: bool = Field(default=False, alias="isFirstLogin")
    mfa_enabled: bool = Field(default=False, alias="mfaEnabled")
    mfa_enrollment_required: bool = Field(default=False, alias="mfaEnrollmentRequired")

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)


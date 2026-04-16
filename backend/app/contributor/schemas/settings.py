from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, model_validator


class AccountSummary(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None


class NotificationPreferences(BaseModel):
    task_assignments: bool = True
    review_decisions: bool = True
    sla_reminders: bool = True
    payout_updates: bool = True
    learning: bool = True


class ContributorSettingsResponse(BaseModel):
    account_summary: AccountSummary
    notification_preferences: NotificationPreferences
    language: str = "en"
    timezone: str = "UTC"
    quiet_hours_start: str | None = None  # e.g. "22:00"
    quiet_hours_end: str | None = None  # e.g. "08:00"
    two_factor_enabled: bool = False


class PatchAccountBody(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)


class PatchNotificationsBody(BaseModel):
    task_assignments: bool | None = None
    review_decisions: bool | None = None
    sla_reminders: bool | None = None
    payout_updates: bool | None = None
    learning: bool | None = None


class PatchLocaleBody(BaseModel):
    language: str | None = Field(default=None, min_length=2, max_length=16)
    timezone: str | None = Field(default=None, max_length=64)
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)

    @model_validator(mode="after")
    def passwords_match(self) -> ChangePasswordBody:
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match")
        return self


class TwoFactorSetupResponse(BaseModel):
    qr_code_url: str
    secret: str
    manual_code: str


class TwoFactorVerifyBody(BaseModel):
    verification_code: str = Field(min_length=6, max_length=10)


class TwoFactorDisableBody(BaseModel):
    password: str | None = None
    verification_code: str | None = None

    @model_validator(mode="after")
    def require_password_or_code(self) -> TwoFactorDisableBody:
        if not self.password and not self.verification_code:
            raise ValueError("Provide password or verification_code")
        return self


class DeactivateAccountBody(BaseModel):
    confirmation_text: str = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=2000)
    password: str | None = None

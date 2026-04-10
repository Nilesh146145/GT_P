from datetime import datetime

from pydantic import BaseModel, Field


class MilestonePaymentLine(BaseModel):
    milestone_key: str
    label: str
    amount_cents: int
    currency: str = "USD"
    status: str = Field(description="e.g. pending, released, invoiced")


class CommercialSummaryResponse(BaseModel):
    project_id: str
    contract_value_cents: int
    currency: str = "USD"
    milestone_payments: list[MilestonePaymentLine]
    budget_utilisation_pct: float = Field(ge=0, le=100)


class SendOtpRequest(BaseModel):
    purpose: str = Field(
        description="Use m2_payment or uat_signoff (TAB-8 flows).",
    )
    project_id: str


class SendOtpResponse(BaseModel):
    challenge_id: str
    expires_at: datetime
    message: str
    demo_otp: str | None = Field(
        default=None,
        description="Demo only - do not return in production.",
    )


class OtpConfirmBody(BaseModel):
    otp: str = Field(min_length=4)
    challenge_id: str | None = Field(
        default=None,
        description="Optional; otherwise latest challenge for this flow is used.",
    )


class M2ConfirmResponse(BaseModel):
    project_id: str
    status: str = "m2_otp_verified"
    message: str


class M2ReleaseResponse(BaseModel):
    project_id: str
    status: str = "m2_payment_released"
    released_at: datetime
    amount_cents: int
    currency: str = "USD"


class UatSignoffResponse(BaseModel):
    project_id: str
    status: str = "otp_required"
    challenge_id: str
    expires_at: datetime
    message: str
    demo_otp: str | None = None


class UatConfirmResponse(BaseModel):
    project_id: str
    status: str = "m3_invoice_triggered"
    invoice_id: str
    message: str


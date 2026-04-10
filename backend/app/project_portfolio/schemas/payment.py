from datetime import datetime

from pydantic import BaseModel, Field


class PendingPaymentItem(BaseModel):
    """Task / evidence bundle eligible for payment (approved evidence)."""

    payment_id: str
    task_id: str
    task_title: str
    evidence_id: str
    evidence_title: str
    amount_cents: int = Field(description="Minor units, e.g. USD cents")
    currency: str = "USD"
    approved_at: datetime


class PendingPaymentsResponse(BaseModel):
    project_id: str
    pending: list[PendingPaymentItem]


class SendOtpResponse(BaseModel):
    payment_id: str
    otp_sent: bool
    expires_at: datetime
    message: str
    demo_otp: str | None = Field(
        default=None,
        description="Populated in this demo so you can call /release without SMS.",
    )


class ReleasePaymentResponse(BaseModel):
    payment_id: str
    status: str = "released"
    released_at: datetime


class HoldPaymentResponse(BaseModel):
    payment_id: str
    status: str = "on_hold"
    escalation_id: str


class PaymentHistoryItem(BaseModel):
    payment_id: str
    task_id: str
    task_title: str
    evidence_id: str
    amount_cents: int
    currency: str = "USD"
    released_at: datetime


class PaymentHistoryResponse(BaseModel):
    project_id: str
    payments: list[PaymentHistoryItem]


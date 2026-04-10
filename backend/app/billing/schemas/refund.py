from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("payment_id", mode="before")
    @classmethod
    def strip_payment_id(cls, value: str) -> str:
        return str(value).strip()

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    payment_id: str
    invoice_id: str
    amount: float
    reason: str | None = None
    status: str
    currency: str
    payer_type: str
    payer_id: str
    created_at: datetime
    updated_at: datetime


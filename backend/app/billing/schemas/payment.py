from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.billing.models.billing import PaymentMethod


class CreatePaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    method: PaymentMethod
    transaction_ref: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] | None = None

    @field_validator("invoice_id", mode="before")
    @classmethod
    def strip_invoice_id(cls, value: str) -> str:
        return str(value).strip()

    @field_validator("transaction_ref")
    @classmethod
    def normalize_transaction_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_id: str
    amount: float
    method: str
    status: str
    transaction_ref: str | None = None
    metadata: dict[str, Any] | None = None
    currency: str
    payer_type: str
    payer_id: str
    created_at: datetime
    updated_at: datetime


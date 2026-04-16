from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InvoiceLineItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., min_length=1, max_length=500)
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    tax_rate: float | None = Field(default=None, ge=0)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("description is required")
        return stripped


class CreateInvoiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payer_type: str = Field(..., min_length=1, max_length=100)
    payer_id: str = Field(..., min_length=1)
    currency: str = Field(..., min_length=1, max_length=10)
    due_at: datetime | None = None
    line_items: list[InvoiceLineItemCreate] = Field(..., min_length=1)
    discount: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("payer_type", "payer_id", "currency", mode="before")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        return str(value).strip()

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class UpdateInvoiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(default=None, min_length=1, max_length=100)
    due_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().lower()
        return stripped or None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class InvoiceLineItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    description: str
    quantity: float
    unit_price: float
    tax_rate: float | None = None
    subtotal: float
    tax_amount: float
    total_amount: float


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    payer_type: str
    payer_id: str
    payer: dict[str, Any] | None = None
    currency: str
    due_at: datetime | None = None
    status: str
    line_items: list[InvoiceLineItemResponse]
    subtotal: float
    tax_total: float
    discount: float
    total_amount: float
    paid_amount: float
    refunded_amount: float
    balance_due: float
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


"""
Billing module (FSD §10) — portfolio grid, milestone invoices, enterprise billing settings.

Payment model: M1 30% · M2 35% · M3 35% (contracted value from Stage 2 Commercial Review).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

import re

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class MilestoneCode(str, Enum):
    M1 = "m1"
    M2 = "m2"
    M3 = "m3"


class InvoiceDisplayStatus(str, Enum):
    """Statuses shown in All Projects / Invoices (FSD)."""

    PENDING = "PENDING"
    AWAITING_SIGNOFF = "AWAITING_SIGNOFF"
    DUE = "DUE"
    OVERDUE = "OVERDUE"
    PAID = "PAID"


class BillingSettingsUpdate(BaseModel):
    """§10.5 — editable by Enterprise Admin only."""

    model_config = ConfigDict(populate_by_name=True)

    billing_contact_email: EmailStr = Field(
        ...,
        alias="billingContactEmail",
        validation_alias=AliasChoices("billingContactEmail", "billing_contact_email"),
    )
    billing_contact_name: str = Field(
        ...,
        max_length=100,
        alias="billingContactName",
        validation_alias=AliasChoices("billingContactName", "billing_contact_name"),
    )
    billing_address_line1: str = Field(
        ...,
        max_length=100,
        alias="billingAddressLine1",
        validation_alias=AliasChoices("billingAddressLine1", "billing_address_line1"),
    )
    billing_address_line2: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="billingAddressLine2",
        validation_alias=AliasChoices("billingAddressLine2", "billing_address_line2"),
    )
    city: str = Field(..., max_length=50)
    state_province: str = Field(
        ...,
        max_length=80,
        alias="stateProvince",
        validation_alias=AliasChoices("stateProvince", "state_province"),
    )
    postal_code: str = Field(
        ...,
        max_length=32,
        alias="postalCode",
        validation_alias=AliasChoices("postalCode", "postal_code"),
    )
    country: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    gst_or_vat_number: Optional[str] = Field(
        default=None,
        max_length=32,
        alias="gstOrVatNumber",
        validation_alias=AliasChoices("gstOrVatNumber", "gst_or_vat_number"),
    )
    preferred_payment_method: str = Field(
        ...,
        alias="preferredPaymentMethod",
        validation_alias=AliasChoices("preferredPaymentMethod", "preferred_payment_method"),
        description="bank_transfer_neft | imps | rtgs | wallet",
    )
    bank_account_last4: Optional[str] = Field(
        default=None,
        min_length=4,
        max_length=4,
        alias="bankAccountLast4",
        validation_alias=AliasChoices("bankAccountLast4", "bank_account_last4"),
    )
    bank_account_number: Optional[str] = Field(
        default=None,
        alias="bankAccountNumber",
        validation_alias=AliasChoices("bankAccountNumber", "bank_account_number"),
        description="Optional full account for this request only; validated 9–18 digits, not persisted.",
    )
    bank_ifsc: Optional[str] = Field(
        default=None,
        max_length=11,
        alias="bankIfsc",
        validation_alias=AliasChoices("bankIfsc", "bank_ifsc"),
    )

    @field_validator("country")
    @classmethod
    def upper_country(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def apply_bs003_bank_account(self) -> BillingSettingsUpdate:
        """BS-003 — full account number: numeric, 9–18 digits; only last four are stored."""
        raw = self.bank_account_number
        if raw is None or not str(raw).strip():
            return self
        digits = re.sub(r"\s+", "", str(raw).strip())
        if not digits.isdigit() or not (9 <= len(digits) <= 18):
            raise ValueError("Invalid bank account number format.")
        self.bank_account_last4 = digits[-4:]
        return self


class BillingSettingsResponse(BillingSettingsUpdate):
    """Echo stored settings (masked bank)."""

    model_config = ConfigDict(populate_by_name=True)


class CreateBillingProjectRequest(BaseModel):
    """Register a billable project for the enterprise portfolio (M1/M2/M3 placeholders)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=200)
    client_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        alias="clientName",
        validation_alias=AliasChoices("clientName", "client_name"),
    )
    currency: str = Field(default="USD", min_length=3, max_length=3)
    contracted_amount: Optional[float] = Field(
        default=None,
        ge=0,
        alias="contractedAmount",
        validation_alias=AliasChoices("contractedAmount", "contracted_amount"),
    )
    commercial_review_complete: bool = Field(
        default=False,
        alias="commercialReviewComplete",
        validation_alias=AliasChoices("commercialReviewComplete", "commercial_review_complete"),
    )
    uat_signoff_complete: bool = Field(
        default=False,
        alias="uatSignoffComplete",
        validation_alias=AliasChoices("uatSignoffComplete", "uat_signoff_complete"),
        description="Required before M3 can leave AWAITING_SIGNOFF.",
    )


class MilestoneCell(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    milestone: MilestoneCode
    label: str
    amount: float
    status: InvoiceDisplayStatus
    days_overdue: Optional[int] = Field(default=None, alias="daysOverdue")
    days_remaining: Optional[int] = Field(default=None, alias="daysRemaining")
    invoice_id: Optional[str] = Field(default=None, alias="invoiceId")


class PortfolioProjectRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_id: str = Field(alias="projectId")
    name: str
    client_name: str = Field(alias="clientName")
    contracted_display: dict[str, Any] = Field(
        alias="contracted",
        description="value + pendingReview (BILL-003).",
    )
    m1: MilestoneCell
    m2: MilestoneCell
    m3: MilestoneCell
    total_paid: float = Field(alias="totalPaid")
    balance_due: float = Field(alias="balanceDue")
    currency: str


class PortfolioFooter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_contracted: float = Field(alias="totalContracted")
    total_paid: float = Field(alias="totalPaid")
    total_balance: float = Field(alias="totalBalance")
    currency: str


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    projects: list[PortfolioProjectRow]
    footer: PortfolioFooter


class FinancialSnapshot(BaseModel):
    """Dashboard Financial Snapshot — mirrors portfolio footer + overdue hint."""

    model_config = ConfigDict(populate_by_name=True)

    total_contracted: float = Field(alias="totalContracted")
    total_paid: float = Field(alias="totalPaid")
    total_balance_due: float = Field(alias="totalBalanceDue")
    overdue_amount: float = Field(alias="overdueAmount")
    currency: str


class InvoiceListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    number: str
    project_id: str = Field(alias="projectId")
    project_name: str = Field(alias="projectName")
    milestone: MilestoneCode
    milestone_label: str = Field(alias="milestoneLabel")
    amount: float
    currency: str
    raised_at: Optional[datetime] = Field(default=None, alias="raisedAt")
    due_at: Optional[datetime] = Field(default=None, alias="dueAt")
    paid_at: Optional[datetime] = Field(default=None, alias="paidAt")
    status: InvoiceDisplayStatus
    days_overdue: Optional[int] = Field(default=None, alias="daysOverdue")
    days_remaining: Optional[int] = Field(default=None, alias="daysRemaining")


class AdminRaiseInvoiceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    invoice_id: str = Field(alias="invoiceId")
    status: InvoiceDisplayStatus
    raised_at: datetime = Field(alias="raisedAt")
    due_at: datetime = Field(alias="dueAt")


class AdminConfirmPaymentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    invoice_id: str = Field(alias="invoiceId")
    status: InvoiceDisplayStatus = InvoiceDisplayStatus.PAID
    paid_at: datetime = Field(alias="paidAt")


class BulkInvoicePdfZipRequest(BaseModel):
    """§10.2.4 — bulk PDF pack by raised-date range (optional; all eligible if omitted)."""

    model_config = ConfigDict(populate_by_name=True)

    raised_from: Optional[datetime] = Field(default=None, alias="raisedFrom")
    raised_to: Optional[datetime] = Field(default=None, alias="raisedTo")

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, model_validator


class PreferredMethod(str, Enum):
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    PAYPAL = "paypal"
    UPI = "upi"
    CRYPTO = "crypto"


class PayoutPreferences(BaseModel):
    preferred_method: PreferredMethod
    minimum_payout_amount: Optional[Decimal] = None
    auto_payout: bool = False
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    routing_code: Optional[str] = None
    country: Optional[str] = None
    provider: Optional[str] = None
    phone_number: Optional[str] = None
    paypal_email: Optional[str] = None
    upi_id: Optional[str] = None
    wallet_address: Optional[str] = None
    network: Optional[str] = None
    token: Optional[str] = None


class PayoutPreferencesUpdate(BaseModel):
    preferred_method: PreferredMethod
    minimum_payout_amount: Optional[Decimal] = None
    auto_payout: Optional[bool] = None
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    routing_code: Optional[str] = None
    country: Optional[str] = None
    provider: Optional[str] = None
    phone_number: Optional[str] = None
    paypal_email: Optional[str] = None
    upi_id: Optional[str] = None
    wallet_address: Optional[str] = None
    network: Optional[str] = None
    token: Optional[str] = None

    @model_validator(mode="after")
    def validate_method_fields(self) -> PayoutPreferencesUpdate:
        m = self.preferred_method
        missing: list[str] = []

        def req(name: str, val: Optional[str]) -> None:
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(name)

        if m == PreferredMethod.BANK_TRANSFER:
            for field in (
                "account_name",
                "account_number",
                "bank_name",
                "routing_code",
                "country",
            ):
                req(field, getattr(self, field))
        elif m == PreferredMethod.MOBILE_MONEY:
            req("provider", self.provider)
            req("phone_number", self.phone_number)
        elif m == PreferredMethod.PAYPAL:
            req("paypal_email", self.paypal_email)
        elif m == PreferredMethod.UPI:
            req("upi_id", self.upi_id)
        elif m == PreferredMethod.CRYPTO:
            req("wallet_address", self.wallet_address)
            req("network", self.network)
            req("token", self.token)

        if missing:
            raise ValueError(
                f"Missing required fields for {m.value}: {', '.join(missing)}"
            )
        return self

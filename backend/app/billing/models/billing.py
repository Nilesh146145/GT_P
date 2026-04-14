from __future__ import annotations

from enum import Enum


BILLING_INVOICES_COLLECTION = "billing_invoices"
BILLING_INVOICE_ITEMS_COLLECTION = "billing_invoice_items"
BILLING_PAYMENTS_COLLECTION = "billing_payments"
BILLING_REFUNDS_COLLECTION = "billing_refunds"


class PaymentMethod(str, Enum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"
    UPI = "upi"
    CRYPTO = "crypto"
    WALLET = "wallet"


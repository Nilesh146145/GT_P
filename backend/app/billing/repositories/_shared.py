from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.billing.models.billing import (
    BILLING_INVOICES_COLLECTION,
    BILLING_INVOICE_ITEMS_COLLECTION,
    BILLING_PAYMENTS_COLLECTION,
    BILLING_REFUNDS_COLLECTION,
)
from app.core.database import get_database


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_object_id(raw: str, *, field_name: str) -> ObjectId:
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}.",
        ) from exc


def invoices_collection():
    return get_database()[BILLING_INVOICES_COLLECTION]


def invoice_items_collection():
    return get_database()[BILLING_INVOICE_ITEMS_COLLECTION]


def payments_collection():
    return get_database()[BILLING_PAYMENTS_COLLECTION]


def refunds_collection():
    return get_database()[BILLING_REFUNDS_COLLECTION]


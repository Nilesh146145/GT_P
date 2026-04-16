from __future__ import annotations

from typing import Any

from app.billing.repositories._shared import payments_collection, to_object_id


async def create_payment(payment_doc: dict[str, Any]) -> dict[str, Any]:
    result = await payments_collection().insert_one(payment_doc)
    return await find_payment_by_id(str(result.inserted_id))


async def find_payment_by_id(payment_id: str) -> dict[str, Any] | None:
    return await payments_collection().find_one({"_id": to_object_id(payment_id, field_name="payment_id")})


async def list_payments(
    query: dict[str, Any],
    *,
    page: int,
    page_size: int,
) -> list[dict[str, Any]]:
    skip = max(0, (page - 1) * page_size)
    cursor = payments_collection().find(query).sort("created_at", -1).skip(skip).limit(page_size)
    return await cursor.to_list(length=page_size)


async def list_payments_for_invoice(invoice_id: str) -> list[dict[str, Any]]:
    return await payments_collection().find({"invoice_id": invoice_id}).sort("created_at", -1).to_list(length=500)


async def sum_completed_payments_by_invoice(invoice_ids: list[str]) -> dict[str, float]:
    if not invoice_ids:
        return {}
    totals = {invoice_id: 0.0 for invoice_id in invoice_ids}
    cursor = payments_collection().find(
        {
            "invoice_id": {"$in": invoice_ids},
            "status": {"$in": ["completed", "paid", "succeeded"]},
        }
    )
    async for payment in cursor:
        totals[payment["invoice_id"]] = round(
            totals.get(payment["invoice_id"], 0.0) + float(payment.get("amount") or 0.0),
            2,
        )
    return totals


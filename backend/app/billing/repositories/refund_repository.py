from __future__ import annotations

from typing import Any

from app.billing.repositories._shared import refunds_collection, to_object_id


async def create_refund(refund_doc: dict[str, Any]) -> dict[str, Any]:
    result = await refunds_collection().insert_one(refund_doc)
    return await find_refund_by_id(str(result.inserted_id))


async def find_refund_by_id(refund_id: str) -> dict[str, Any] | None:
    return await refunds_collection().find_one({"_id": to_object_id(refund_id, field_name="refund_id")})


async def list_refunds(query: dict[str, Any]) -> list[dict[str, Any]]:
    return await refunds_collection().find(query).sort("created_at", -1).to_list(length=500)


async def list_refunds_for_invoice(invoice_id: str) -> list[dict[str, Any]]:
    return await refunds_collection().find({"invoice_id": invoice_id}).sort("created_at", -1).to_list(length=500)


async def sum_refunds_by_invoice(invoice_ids: list[str]) -> dict[str, float]:
    if not invoice_ids:
        return {}
    totals = {invoice_id: 0.0 for invoice_id in invoice_ids}
    cursor = refunds_collection().find(
        {
            "invoice_id": {"$in": invoice_ids},
            "status": {"$in": ["processed", "completed", "succeeded"]},
        }
    )
    async for refund in cursor:
        totals[refund["invoice_id"]] = round(
            totals.get(refund["invoice_id"], 0.0) + float(refund.get("amount") or 0.0),
            2,
        )
    return totals


async def sum_refunds_for_payment(payment_id: str) -> float:
    total = 0.0
    cursor = refunds_collection().find(
        {
            "payment_id": payment_id,
            "status": {"$in": ["processed", "completed", "succeeded"]},
        }
    )
    async for refund in cursor:
        total = round(total + float(refund.get("amount") or 0.0), 2)
    return total

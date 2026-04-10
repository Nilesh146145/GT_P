from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING

from app.billing.repositories._shared import invoice_items_collection, invoices_collection, to_object_id


def _sort_direction(direction: str) -> int:
    return ASCENDING if direction == "asc" else DESCENDING


async def create_invoice(invoice_doc: dict[str, Any], item_docs: list[dict[str, Any]]) -> dict[str, Any]:
    result = await invoices_collection().insert_one(invoice_doc)
    invoice_id = str(result.inserted_id)
    if item_docs:
        for item in item_docs:
            item["invoice_id"] = invoice_id
        await invoice_items_collection().insert_many(item_docs)
    return await find_invoice_by_id(invoice_id)


async def find_invoice_by_id(invoice_id: str) -> dict[str, Any] | None:
    return await invoices_collection().find_one({"_id": to_object_id(invoice_id, field_name="invoice_id")})


async def list_invoices(
    query: dict[str, Any],
    *,
    sort_field: str,
    sort_dir: str,
    page: int,
    page_size: int,
) -> list[dict[str, Any]]:
    skip = max(0, (page - 1) * page_size)
    cursor = (
        invoices_collection()
        .find(query)
        .sort(sort_field, _sort_direction(sort_dir))
        .skip(skip)
        .limit(page_size)
    )
    return await cursor.to_list(length=page_size)


async def list_all_invoices(query: dict[str, Any]) -> list[dict[str, Any]]:
    return await invoices_collection().find(query).to_list(length=5000)


async def update_invoice(invoice_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    await invoices_collection().update_one(
        {"_id": to_object_id(invoice_id, field_name="invoice_id")},
        {"$set": fields},
    )
    return await find_invoice_by_id(invoice_id)


async def list_items_for_invoice(invoice_id: str) -> list[dict[str, Any]]:
    return await invoice_items_collection().find({"invoice_id": invoice_id}).to_list(length=500)


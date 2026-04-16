from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.billing.repositories import invoice_repository, payment_repository, reference_repository, refund_repository
from app.billing.repositories._shared import utc_now
from app.billing.schemas.invoice import (
    CreateInvoiceRequest,
    InvoiceLineItemResponse,
    InvoiceResponse,
    UpdateInvoiceRequest,
)
from app.billing.services._common import (
    contributor_scope_filter,
    current_user_id,
    ensure_invoice_access,
    is_admin_like,
    monetary,
    normalize_invoice_status,
    resolved_invoice_status,
)

_SORT_FIELD_MAP = {
    "date": "created_at",
    "amount": "total_amount",
    "status": "status",
}


def _build_line_item_documents(payload: CreateInvoiceRequest, now) -> tuple[list[dict[str, Any]], float, float]:
    item_docs: list[dict[str, Any]] = []
    subtotal = 0.0
    tax_total = 0.0
    for item in payload.line_items:
        line_subtotal = monetary(item.quantity * item.unit_price)
        tax_rate = monetary(item.tax_rate or 0.0)
        tax_amount = monetary(line_subtotal * (tax_rate / 100 if tax_rate else 0.0))
        total_amount = monetary(line_subtotal + tax_amount)
        subtotal = monetary(subtotal + line_subtotal)
        tax_total = monetary(tax_total + tax_amount)
        item_docs.append(
            {
                "description": item.description,
                "quantity": monetary(item.quantity),
                "unit_price": monetary(item.unit_price),
                "tax_rate": tax_rate if item.tax_rate is not None else None,
                "subtotal": line_subtotal,
                "tax_amount": tax_amount,
                "total_amount": total_amount,
                "created_at": now,
                "updated_at": now,
            }
        )
    return item_docs, subtotal, tax_total


async def build_invoice_response(invoice_doc: dict[str, Any]) -> InvoiceResponse:
    invoice_id = str(invoice_doc["_id"])
    item_docs = await invoice_repository.list_items_for_invoice(invoice_id)
    payment_totals = await payment_repository.sum_completed_payments_by_invoice([invoice_id])
    refund_totals = await refund_repository.sum_refunds_by_invoice([invoice_id])
    paid_amount = monetary(payment_totals.get(invoice_id, 0.0))
    refunded_amount = monetary(refund_totals.get(invoice_id, 0.0))
    net_paid = monetary(max(0.0, paid_amount - refunded_amount))
    total_amount = monetary(invoice_doc.get("total_amount") or 0.0)
    payer = await reference_repository.get_payer_summary(invoice_doc.get("payer_type", ""), invoice_doc.get("payer_id", ""))
    status_value = resolved_invoice_status(
        invoice_doc,
        paid_amount=paid_amount,
        refunded_amount=refunded_amount,
    )

    return InvoiceResponse(
        id=invoice_id,
        payer_type=invoice_doc["payer_type"],
        payer_id=invoice_doc["payer_id"],
        payer=payer,
        currency=invoice_doc["currency"],
        due_at=invoice_doc.get("due_at"),
        status=status_value,
        line_items=[
            InvoiceLineItemResponse(
                id=str(item["_id"]),
                description=item["description"],
                quantity=monetary(item["quantity"]),
                unit_price=monetary(item["unit_price"]),
                tax_rate=item.get("tax_rate"),
                subtotal=monetary(item["subtotal"]),
                tax_amount=monetary(item["tax_amount"]),
                total_amount=monetary(item["total_amount"]),
            )
            for item in item_docs
        ],
        subtotal=monetary(invoice_doc.get("subtotal") or 0.0),
        tax_total=monetary(invoice_doc.get("tax_total") or 0.0),
        discount=monetary(invoice_doc.get("discount") or 0.0),
        total_amount=total_amount,
        paid_amount=paid_amount,
        refunded_amount=refunded_amount,
        balance_due=monetary(max(0.0, total_amount - net_paid)),
        notes=invoice_doc.get("notes"),
        created_at=invoice_doc["created_at"],
        updated_at=invoice_doc["updated_at"],
    )


async def create_invoice(current_user: dict, payload: CreateInvoiceRequest) -> dict[str, Any]:
    now = utc_now()
    item_docs, subtotal, tax_total = _build_line_item_documents(payload, now)
    discount = monetary(payload.discount or 0.0)
    total_amount = monetary(max(0.0, subtotal + tax_total - discount))
    user_id = current_user_id(current_user)

    invoice_doc = {
        "payer_type": payload.payer_type,
        "payer_id": payload.payer_id,
        "currency": payload.currency,
        "due_at": payload.due_at,
        "status": "pending",
        "subtotal": subtotal,
        "tax_total": tax_total,
        "discount": discount,
        "total_amount": total_amount,
        "notes": payload.notes,
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
        "created_at": now,
        "updated_at": now,
    }
    created = await invoice_repository.create_invoice(invoice_doc, item_docs)
    return (await build_invoice_response(created)).model_dump(mode="json")


async def list_invoices(
    current_user: dict,
    *,
    status_filter: str | None,
    date_from,
    date_to,
    page: int,
    page_size: int,
    sort_by: str,
    sort_dir: str,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if not is_admin_like(current_user):
        query.update(contributor_scope_filter(current_user))

    created_at_filter: dict[str, Any] = {}
    if date_from is not None:
        created_at_filter["$gte"] = date_from
    if date_to is not None:
        created_at_filter["$lte"] = date_to
    if created_at_filter:
        query["created_at"] = created_at_filter

    invoices = await invoice_repository.list_invoices(
        query,
        sort_field=_SORT_FIELD_MAP[sort_by],
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )

    items = [await build_invoice_response(invoice_doc) for invoice_doc in invoices]
    if status_filter:
        normalized = normalize_invoice_status(status_filter)
        items = [item for item in items if item.status == normalized]
    return [item.model_dump(mode="json") for item in items]


async def get_invoice(current_user: dict, invoice_id: str) -> dict[str, Any]:
    invoice_doc = await invoice_repository.find_invoice_by_id(invoice_id)
    invoice_doc = ensure_invoice_access(current_user, invoice_doc)
    return (await build_invoice_response(invoice_doc)).model_dump(mode="json")


async def update_invoice(current_user: dict, invoice_id: str, payload: UpdateInvoiceRequest) -> dict[str, Any]:
    invoice_doc = await invoice_repository.find_invoice_by_id(invoice_id)
    invoice_doc = ensure_invoice_access(current_user, invoice_doc)

    fields: dict[str, Any] = {
        "updated_at": utc_now(),
        "updated_by_user_id": current_user_id(current_user),
    }
    if payload.status is not None:
        fields["status"] = normalize_invoice_status(payload.status)
    if payload.due_at is not None:
        fields["due_at"] = payload.due_at
    if payload.notes is not None:
        fields["notes"] = payload.notes

    updated = await invoice_repository.update_invoice(invoice_id, fields)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    return (await build_invoice_response(updated)).model_dump(mode="json")


async def get_invoice_for_payment(current_user: dict, invoice_id: str) -> dict[str, Any]:
    invoice_doc = await invoice_repository.find_invoice_by_id(invoice_id)
    return ensure_invoice_access(current_user, invoice_doc)


async def get_invoice_detail_model(current_user: dict, invoice_id: str) -> InvoiceResponse:
    invoice_doc = await invoice_repository.find_invoice_by_id(invoice_id)
    invoice_doc = ensure_invoice_access(current_user, invoice_doc)
    return await build_invoice_response(invoice_doc)


async def update_invoice_status_from_balances(invoice_id: str, *, status_value: str, updated_by_user_id: str) -> None:
    await invoice_repository.update_invoice(
        invoice_id,
        {
            "status": status_value,
            "updated_at": utc_now(),
            "updated_by_user_id": updated_by_user_id,
        },
    )

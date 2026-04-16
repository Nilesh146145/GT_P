from __future__ import annotations

from fastapi import HTTPException

from app.billing.repositories import payment_repository, refund_repository
from app.billing.repositories._shared import utc_now
from app.billing.schemas.payment import CreatePaymentRequest, PaymentResponse
from app.billing.services import invoice_service
from app.billing.services._common import (
    contributor_scope_filter,
    current_user_id,
    ensure_payment_access,
    is_admin_like,
    monetary,
    normalize_invoice_status,
    resolved_invoice_status,
)


def _build_payment_response(payment_doc: dict) -> PaymentResponse:
    return PaymentResponse(
        id=str(payment_doc["_id"]),
        invoice_id=payment_doc["invoice_id"],
        amount=monetary(payment_doc["amount"]),
        method=payment_doc["method"],
        status=payment_doc["status"],
        transaction_ref=payment_doc.get("transaction_ref"),
        metadata=payment_doc.get("metadata"),
        currency=payment_doc["currency"],
        payer_type=payment_doc["payer_type"],
        payer_id=payment_doc["payer_id"],
        created_at=payment_doc["created_at"],
        updated_at=payment_doc["updated_at"],
    )


async def list_payments(
    current_user: dict,
    *,
    status_filter: str | None,
    method: str | None,
    date_from,
    date_to,
    page: int,
    page_size: int,
) -> list[dict]:
    query: dict = {}
    if not is_admin_like(current_user):
        query.update(contributor_scope_filter(current_user))
    if status_filter:
        query["status"] = normalize_invoice_status(status_filter)
    if method:
        query["method"] = method

    created_at_filter: dict = {}
    if date_from is not None:
        created_at_filter["$gte"] = date_from
    if date_to is not None:
        created_at_filter["$lte"] = date_to
    if created_at_filter:
        query["created_at"] = created_at_filter

    items = await payment_repository.list_payments(query, page=page, page_size=page_size)
    return [_build_payment_response(item).model_dump(mode="json") for item in items]


async def create_payment(current_user: dict, payload: CreatePaymentRequest) -> dict:
    invoice_doc = await invoice_service.get_invoice_for_payment(current_user, payload.invoice_id)
    invoice_view = await invoice_service.get_invoice_detail_model(current_user, payload.invoice_id)

    if invoice_view.status in {"cancelled", "void", "refunded"}:
        raise HTTPException(detail="This invoice is not payable.", status_code=400)

    if payload.amount > invoice_view.balance_due:
        raise HTTPException(detail="Payment amount exceeds the outstanding balance.", status_code=400)

    now = utc_now()
    payment_doc = {
        "invoice_id": payload.invoice_id,
        "amount": monetary(payload.amount),
        "method": payload.method.value,
        "status": "completed",
        "transaction_ref": payload.transaction_ref,
        "metadata": payload.metadata,
        "currency": invoice_doc["currency"],
        "payer_type": invoice_doc["payer_type"],
        "payer_id": invoice_doc["payer_id"],
        "created_by_user_id": current_user_id(current_user),
        "created_at": now,
        "updated_at": now,
    }
    created = await payment_repository.create_payment(payment_doc)

    paid_totals = await payment_repository.sum_completed_payments_by_invoice([payload.invoice_id])
    refund_totals = await refund_repository.sum_refunds_by_invoice([payload.invoice_id])
    new_status = resolved_invoice_status(
        invoice_doc,
        paid_amount=paid_totals.get(payload.invoice_id, 0.0),
        refunded_amount=refund_totals.get(payload.invoice_id, 0.0),
    )
    await invoice_service.update_invoice_status_from_balances(
        payload.invoice_id,
        status_value=new_status,
        updated_by_user_id=current_user_id(current_user),
    )

    return _build_payment_response(created).model_dump(mode="json")


async def get_payment(current_user: dict, payment_id: str) -> dict:
    payment_doc = await payment_repository.find_payment_by_id(payment_id)
    payment_doc = ensure_payment_access(current_user, payment_doc)
    return _build_payment_response(payment_doc).model_dump(mode="json")

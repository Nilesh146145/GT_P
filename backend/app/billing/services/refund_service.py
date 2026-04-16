from __future__ import annotations

from fastapi import HTTPException

from app.billing.repositories import payment_repository, refund_repository
from app.billing.repositories._shared import utc_now
from app.billing.schemas.refund import CreateRefundRequest, RefundResponse
from app.billing.services import invoice_service
from app.billing.services._common import (
    contributor_scope_filter,
    current_user_id,
    ensure_payment_access,
    ensure_refund_access,
    is_admin_like,
    monetary,
    resolved_invoice_status,
)


def _build_refund_response(refund_doc: dict) -> RefundResponse:
    return RefundResponse(
        id=str(refund_doc["_id"]),
        payment_id=refund_doc["payment_id"],
        invoice_id=refund_doc["invoice_id"],
        amount=monetary(refund_doc["amount"]),
        reason=refund_doc.get("reason"),
        status=refund_doc["status"],
        currency=refund_doc["currency"],
        payer_type=refund_doc["payer_type"],
        payer_id=refund_doc["payer_id"],
        created_at=refund_doc["created_at"],
        updated_at=refund_doc["updated_at"],
    )


async def create_refund(current_user: dict, payload: CreateRefundRequest) -> dict:
    payment_doc = await payment_repository.find_payment_by_id(payload.payment_id)
    payment_doc = ensure_payment_access(current_user, payment_doc)

    refundable_amount = monetary(payment_doc["amount"] - await refund_repository.sum_refunds_for_payment(payload.payment_id))
    if payload.amount > refundable_amount:
        raise HTTPException(detail="Refund amount exceeds the remaining refundable balance.", status_code=400)

    now = utc_now()
    refund_doc = {
        "payment_id": payload.payment_id,
        "invoice_id": payment_doc["invoice_id"],
        "amount": monetary(payload.amount),
        "reason": payload.reason,
        "status": "processed",
        "currency": payment_doc["currency"],
        "payer_type": payment_doc["payer_type"],
        "payer_id": payment_doc["payer_id"],
        "created_by_user_id": current_user_id(current_user),
        "created_at": now,
        "updated_at": now,
    }
    created = await refund_repository.create_refund(refund_doc)

    invoice_doc = await invoice_service.get_invoice_for_payment(current_user, payment_doc["invoice_id"])
    paid_totals = await payment_repository.sum_completed_payments_by_invoice([payment_doc["invoice_id"]])
    refund_totals = await refund_repository.sum_refunds_by_invoice([payment_doc["invoice_id"]])
    new_status = resolved_invoice_status(
        invoice_doc,
        paid_amount=paid_totals.get(payment_doc["invoice_id"], 0.0),
        refunded_amount=refund_totals.get(payment_doc["invoice_id"], 0.0),
    )
    await invoice_service.update_invoice_status_from_balances(
        payment_doc["invoice_id"],
        status_value=new_status,
        updated_by_user_id=current_user_id(current_user),
    )

    return _build_refund_response(created).model_dump(mode="json")


async def list_refunds(current_user: dict) -> list[dict]:
    query: dict = {}
    if not is_admin_like(current_user):
        query.update(contributor_scope_filter(current_user))
    items = await refund_repository.list_refunds(query)
    return [_build_refund_response(item).model_dump(mode="json") for item in items]


async def get_refund(current_user: dict, refund_id: str) -> dict:
    refund_doc = await refund_repository.find_refund_by_id(refund_id)
    refund_doc = ensure_refund_access(current_user, refund_doc)
    return _build_refund_response(refund_doc).model_dump(mode="json")

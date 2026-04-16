from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status


_ENTERPRISE_ROLE_ALIASES = frozenset(
    {
        "enterprise",
        "enterprise_user",
        "enterpriseuser",
        "org_admin",
        "organization_admin",
        "organisation_admin",
    }
)

_TERMINAL_INVOICE_STATUSES = frozenset({"cancelled", "void"})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_role(raw: Any) -> str:
    if raw is None:
        return "enterprise"
    normalized = str(raw).strip().lower()
    if not normalized:
        return "enterprise"
    if normalized in _ENTERPRISE_ROLE_ALIASES:
        return "enterprise"
    return normalized


def is_admin_like(current_user: dict) -> bool:
    return normalize_role(current_user.get("role")) in {"enterprise", "admin"}


def current_user_id(current_user: dict) -> str:
    return str(current_user.get("id") or current_user.get("_id"))


def contributor_scope_filter(current_user: dict) -> dict[str, Any]:
    user_id = current_user_id(current_user)
    return {
        "$or": [
            {"payer_id": user_id},
            {"created_by_user_id": user_id},
        ]
    }


def ensure_invoice_access(current_user: dict, invoice_doc: dict[str, Any] | None) -> dict[str, Any]:
    if not invoice_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    if is_admin_like(current_user):
        return invoice_doc

    user_id = current_user_id(current_user)
    if invoice_doc.get("payer_id") == user_id or invoice_doc.get("created_by_user_id") == user_id:
        return invoice_doc

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")


def ensure_payment_access(current_user: dict, payment_doc: dict[str, Any] | None) -> dict[str, Any]:
    if not payment_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")
    if is_admin_like(current_user):
        return payment_doc

    user_id = current_user_id(current_user)
    if payment_doc.get("payer_id") == user_id or payment_doc.get("created_by_user_id") == user_id:
        return payment_doc

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")


def ensure_refund_access(current_user: dict, refund_doc: dict[str, Any] | None) -> dict[str, Any]:
    if not refund_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found.")
    if is_admin_like(current_user):
        return refund_doc

    user_id = current_user_id(current_user)
    if refund_doc.get("payer_id") == user_id or refund_doc.get("created_by_user_id") == user_id:
        return refund_doc

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found.")


def normalize_invoice_status(raw: str | None) -> str:
    if raw is None:
        return "pending"
    normalized = str(raw).strip().lower()
    return normalized or "pending"


def resolved_invoice_status(
    invoice_doc: dict[str, Any],
    *,
    paid_amount: float,
    refunded_amount: float,
) -> str:
    stored = normalize_invoice_status(invoice_doc.get("status"))
    total_amount = float(invoice_doc.get("total_amount") or 0.0)
    due_at = invoice_doc.get("due_at")
    if due_at and due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)

    net_paid = max(0.0, round(paid_amount - refunded_amount, 2))
    if stored in _TERMINAL_INVOICE_STATUSES:
        return stored
    if paid_amount > 0 and refunded_amount >= paid_amount:
        return "refunded"
    if total_amount > 0 and net_paid >= round(total_amount, 2):
        return "paid"
    if net_paid > 0:
        if due_at and due_at < utc_now():
            return "overdue"
        return "partial"
    if due_at and due_at < utc_now() and stored not in {"draft"}:
        return "overdue"
    return stored


def monetary(value: float) -> float:
    return round(float(value or 0.0), 2)

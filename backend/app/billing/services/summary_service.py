from __future__ import annotations

from collections import Counter

from app.billing.repositories import invoice_repository, payment_repository, refund_repository
from app.billing.schemas.summary import BillingSummaryResponse
from app.billing.services._common import contributor_scope_filter, is_admin_like, monetary, resolved_invoice_status


async def get_summary(current_user: dict) -> dict:
    query: dict = {}
    if not is_admin_like(current_user):
        query.update(contributor_scope_filter(current_user))

    invoices = await invoice_repository.list_all_invoices(query)
    invoice_ids = [str(invoice["_id"]) for invoice in invoices]
    payment_totals = await payment_repository.sum_completed_payments_by_invoice(invoice_ids)
    refund_totals = await refund_repository.sum_refunds_by_invoice(invoice_ids)

    total_invoiced = 0.0
    total_paid = 0.0
    total_pending = 0.0
    total_overdue = 0.0
    currencies = Counter()

    for invoice in invoices:
        invoice_id = str(invoice["_id"])
        total_amount = monetary(invoice.get("total_amount") or 0.0)
        paid_amount = monetary(payment_totals.get(invoice_id, 0.0))
        refunded_amount = monetary(refund_totals.get(invoice_id, 0.0))
        net_paid = monetary(max(0.0, paid_amount - refunded_amount))
        balance_due = monetary(max(0.0, total_amount - net_paid))
        status_value = resolved_invoice_status(
            invoice,
            paid_amount=paid_amount,
            refunded_amount=refunded_amount,
        )

        total_invoiced = monetary(total_invoiced + total_amount)
        total_paid = monetary(total_paid + net_paid)
        if status_value == "overdue":
            total_overdue = monetary(total_overdue + balance_due)
        elif status_value != "paid":
            total_pending = monetary(total_pending + balance_due)
        currencies[str(invoice.get("currency") or "USD").upper()] += 1

    currency = "USD"
    if currencies:
        currency = currencies.most_common(1)[0][0]
        if len(currencies) > 1:
            currency = "MULTI"

    return BillingSummaryResponse(
        total_invoiced=total_invoiced,
        total_paid=total_paid,
        total_pending=total_pending,
        total_overdue=total_overdue,
        currency=currency,
    ).model_dump(mode="json")


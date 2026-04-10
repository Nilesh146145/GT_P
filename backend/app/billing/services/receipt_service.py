from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.billing.repositories import payment_repository, refund_repository
from app.billing.services import invoice_service


def _fmt_amount(value: float, currency: str) -> str:
    return f"{currency} {value:,.2f}"


async def build_invoice_receipt_pdf(current_user: dict, invoice_id: str) -> tuple[bytes, str]:
    invoice = await invoice_service.get_invoice_detail_model(current_user, invoice_id)
    payments = await payment_repository.list_payments_for_invoice(invoice_id)
    refunds = await refund_repository.list_refunds_for_invoice(invoice_id)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 20 * mm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20 * mm, y, "Invoice Receipt")
    y -= 10 * mm

    pdf.setFont("Helvetica", 10)
    summary_lines = [
        f"Invoice ID: {invoice.id}",
        f"Status: {invoice.status}",
        f"Payer Type: {invoice.payer_type}",
        f"Payer ID: {invoice.payer_id}",
        f"Currency: {invoice.currency}",
        f"Total Amount: {_fmt_amount(invoice.total_amount, invoice.currency)}",
        f"Paid Amount: {_fmt_amount(invoice.paid_amount, invoice.currency)}",
        f"Refunded Amount: {_fmt_amount(invoice.refunded_amount, invoice.currency)}",
        f"Balance Due: {_fmt_amount(invoice.balance_due, invoice.currency)}",
    ]
    for line in summary_lines:
        pdf.drawString(20 * mm, y, line)
        y -= 6 * mm

    y -= 2 * mm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(20 * mm, y, "Line Items")
    y -= 7 * mm

    pdf.setFont("Helvetica", 10)
    for item in invoice.line_items:
        pdf.drawString(
            20 * mm,
            y,
            f"{item.description} | qty {item.quantity:g} | unit {_fmt_amount(item.unit_price, invoice.currency)} | total {_fmt_amount(item.total_amount, invoice.currency)}",
        )
        y -= 6 * mm
        if y < 25 * mm:
            pdf.showPage()
            y = height - 20 * mm
            pdf.setFont("Helvetica", 10)

    y -= 2 * mm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(20 * mm, y, "Payments")
    y -= 7 * mm
    pdf.setFont("Helvetica", 10)
    if payments:
        for payment in payments:
            pdf.drawString(
                20 * mm,
                y,
                f"{payment.get('method')} | {_fmt_amount(float(payment.get('amount') or 0.0), payment.get('currency') or invoice.currency)} | {payment.get('status')}",
            )
            y -= 6 * mm
            if y < 25 * mm:
                pdf.showPage()
                y = height - 20 * mm
                pdf.setFont("Helvetica", 10)
    else:
        pdf.drawString(20 * mm, y, "No payments recorded.")
        y -= 6 * mm

    y -= 2 * mm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(20 * mm, y, "Refunds")
    y -= 7 * mm
    pdf.setFont("Helvetica", 10)
    if refunds:
        for refund in refunds:
            pdf.drawString(
                20 * mm,
                y,
                f"{refund.get('status')} | {_fmt_amount(float(refund.get('amount') or 0.0), refund.get('currency') or invoice.currency)} | {refund.get('reason') or 'No reason'}",
            )
            y -= 6 * mm
            if y < 25 * mm:
                pdf.showPage()
                y = height - 20 * mm
                pdf.setFont("Helvetica", 10)
    else:
        pdf.drawString(20 * mm, y, "No refunds recorded.")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue(), f"invoice-{invoice.id}-receipt.pdf"

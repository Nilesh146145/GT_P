"""
GST-style milestone invoice PDFs (FSD §10.2) — issued in the name of Baarez Technology Solutions Pvt. Ltd.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from fpdf import FPDF

ISSUER_NAME = "Baarez Technology Solutions Pvt. Ltd."


def _pdf_safe(text: str) -> str:
    """Helvetica core font is latin-1; strip/replace common unicode punctuation."""
    return (
        (text or "")
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2122", "")
    )


ISSUER_NOTE = (
    "GlimmoraTeam commercial milestone invoice - document retrieval only; not editable after issue."
)


def safe_filename_part(name: str, max_len: int = 72) -> str:
    """ZIP/PDF filename segment (§10.2.4)."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "").strip()).strip("-")
    return (s[:max_len] if s else "Project")


def format_display_date(dt: Optional[datetime]) -> str:
    if not dt:
        return "-"
    return dt.strftime("%d %b %Y")


def build_milestone_invoice_pdf(
    *,
    invoice_number: str,
    project_name: str,
    milestone_label: str,
    amount: float,
    currency: str,
    raised_at: Optional[datetime],
    due_at: Optional[datetime],
    bill_to_lines: list[str],
    gst_or_vat: Optional[str],
) -> bytes:
    """Single-page PDF suitable for PAID / DUE / OVERDUE milestone invoices."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 8, _pdf_safe("Tax Invoice"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 5, _pdf_safe(ISSUER_NAME), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 4, _pdf_safe(ISSUER_NOTE))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(42, 6, "Invoice number", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, _pdf_safe(invoice_number), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(42, 6, "Project", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, _pdf_safe(project_name), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(42, 6, "Milestone", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, _pdf_safe(milestone_label), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(42, 6, "Raised date", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, format_display_date(raised_at), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(42, 6, "Due date", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, format_display_date(due_at), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Bill to", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for line in bill_to_lines:
        if line.strip():
            pdf.cell(0, 5, _pdf_safe(line.strip()), new_x="LMARGIN", new_y="NEXT")
    if gst_or_vat:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, _pdf_safe(f"GSTIN / VAT: {gst_or_vat}"), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, f"Amount due: {amount:,.2f} {currency}", new_x="LMARGIN", new_y="NEXT")
    raw = pdf.output()
    return bytes(raw)

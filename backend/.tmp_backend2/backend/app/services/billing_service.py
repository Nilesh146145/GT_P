"""
Billing (FSD §10) — portfolio grid, invoices, settings, admin raise/confirm payment.
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from pymongo import ReturnDocument

from app.core.database import (
    get_billing_counters_collection,
    get_billing_invoices_collection,
    get_billing_projects_collection,
    get_enterprises_collection,
)
from app.services import billing_pdf
from app.schemas.billing import (
    AdminConfirmPaymentResponse,
    AdminRaiseInvoiceResponse,
    BillingSettingsResponse,
    BillingSettingsUpdate,
    CreateBillingProjectRequest,
    FinancialSnapshot,
    InvoiceDisplayStatus,
    InvoiceListItem,
    MilestoneCell,
    MilestoneCode,
    PortfolioFooter,
    PortfolioProjectRow,
    PortfolioResponse,
)

MILESTONE_PCT = {
    MilestoneCode.M1: 0.30,
    MilestoneCode.M2: 0.35,
    MilestoneCode.M3: 0.35,
}

MILESTONE_LABEL = {
    MilestoneCode.M1: "M1 — SOW Onboarding",
    MilestoneCode.M2: "M2 — Development",
    MilestoneCode.M3: "M3 — UAT Sign-off",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="Invalid id.") from exc


async def _next_invoice_number() -> str:
    """GT-YYYY-NNN unique per year (INV-003)."""
    year = _utc_now().year
    col = get_billing_counters_collection()
    doc = await col.find_one_and_update(
        {"_id": f"inv-{year}"},
        {"$inc": {"seq": 1}, "$setOnInsert": {"year": year}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    seq = int(doc.get("seq", 1))
    return f"GT-{year}-{seq:03d}"


def _split_amounts(contracted: float) -> dict[MilestoneCode, float]:
    return {
        MilestoneCode.M1: round(contracted * MILESTONE_PCT[MilestoneCode.M1], 2),
        MilestoneCode.M2: round(contracted * MILESTONE_PCT[MilestoneCode.M2], 2),
        MilestoneCode.M3: round(contracted * MILESTONE_PCT[MilestoneCode.M3], 2),
    }


async def sync_invoice_overdue(enterprise_id: str) -> None:
    """Mark stored DUE → OVERDUE when past due window."""
    inv = get_billing_invoices_collection()
    now = _utc_now()
    await inv.update_many(
        {
            "enterprise_id": enterprise_id,
            "lifecycle": "raised",
            "payment_status": "due",
            "due_at": {"$lt": now},
        },
        {"$set": {"payment_status": "overdue", "updated_at": now}},
    )


def _days_overdue(due: Optional[datetime]) -> int:
    if not due:
        return 0
    due = due if due.tzinfo else due.replace(tzinfo=timezone.utc)
    now = _utc_now()
    if due >= now:
        return 0
    return (now - due).days


def _days_remaining(due: Optional[datetime]) -> Optional[int]:
    if not due:
        return None
    due = due if due.tzinfo else due.replace(tzinfo=timezone.utc)
    now = _utc_now()
    if due <= now:
        return 0
    return max(0, (due - now).days)


def _to_display_status(
    inv: dict,
    project: dict,
) -> InvoiceDisplayStatus:
    ms = inv.get("milestone")
    if inv.get("lifecycle") != "raised":
        if ms == "m3" and not project.get("uat_signoff_complete", False):
            return InvoiceDisplayStatus.AWAITING_SIGNOFF
        return InvoiceDisplayStatus.PENDING
    if inv.get("payment_status") == "paid":
        return InvoiceDisplayStatus.PAID
    if inv.get("payment_status") == "overdue":
        return InvoiceDisplayStatus.OVERDUE
    return InvoiceDisplayStatus.DUE


async def create_billing_project(
    enterprise_id: str,
    body: CreateBillingProjectRequest,
) -> dict[str, Any]:
    bproj = get_billing_projects_collection()
    binv = get_billing_invoices_collection()
    now = _utc_now()
    pid = ObjectId()
    project_id = str(pid)

    contracted = body.contracted_amount
    commercial_ok = body.commercial_review_complete and contracted is not None and contracted > 0
    amounts = _split_amounts(float(contracted)) if commercial_ok else {m: 0.0 for m in MilestoneCode}

    proj = {
        "_id": pid,
        "enterprise_id": enterprise_id,
        "name": body.name.strip(),
        "client_name": body.client_name.strip(),
        "currency": body.currency.strip().upper(),
        "contracted_amount": float(contracted) if contracted is not None else None,
        "commercial_review_complete": body.commercial_review_complete,
        "uat_signoff_complete": body.uat_signoff_complete,
        "created_at": now,
        "updated_at": now,
    }
    await bproj.insert_one(proj)

    inv_docs = []
    for m in (MilestoneCode.M1, MilestoneCode.M2, MilestoneCode.M3):
        inv_docs.append(
            {
                "enterprise_id": enterprise_id,
                "project_id": project_id,
                "milestone": m.value,
                "invoice_number": None,
                "amount": amounts[m],
                "currency": proj["currency"],
                "lifecycle": "not_raised",
                "payment_status": "none",
                "raised_at": None,
                "due_at": None,
                "paid_at": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    await binv.insert_many(inv_docs)

    return {"id": project_id, "name": proj["name"], "clientName": proj["client_name"]}


async def get_financial_snapshot(enterprise_id: str) -> FinancialSnapshot:
    portfolio = await get_portfolio(enterprise_id)
    overdue = sum(
        (r.m1.amount if r.m1.status == InvoiceDisplayStatus.OVERDUE else 0)
        + (r.m2.amount if r.m2.status == InvoiceDisplayStatus.OVERDUE else 0)
        + (r.m3.amount if r.m3.status == InvoiceDisplayStatus.OVERDUE else 0)
        for r in portfolio.projects
    )
    return FinancialSnapshot(
        total_contracted=portfolio.footer.total_contracted,
        total_paid=portfolio.footer.total_paid,
        total_balance_due=portfolio.footer.total_balance,
        overdue_amount=round(overdue, 2),
        currency=portfolio.footer.currency,
    )


async def get_portfolio(
    enterprise_id: str,
    *,
    project_ids: Optional[list[str]] = None,
    milestone_status_filter: Optional[list[InvoiceDisplayStatus]] = None,
    sort_by: str = "overdue_first",
) -> PortfolioResponse:
    await sync_invoice_overdue(enterprise_id)
    bproj = get_billing_projects_collection()
    binv = get_billing_invoices_collection()
    projects = await bproj.find({"enterprise_id": enterprise_id}).to_list(500)
    rows: list[PortfolioProjectRow] = []

    for p in projects:
        pid = str(p["_id"])
        invs = (
            await binv.find({"enterprise_id": enterprise_id, "project_id": pid}).to_list(10)
        )
        by_m = {i["milestone"]: i for i in invs}

        commercial_ok = bool(
            p.get("commercial_review_complete") and p.get("contracted_amount") is not None
        )
        contracted_display: dict[str, Any]
        if commercial_ok:
            contracted_display = {"value": float(p["contracted_amount"]), "pendingReview": False}
        else:
            contracted_display = {"value": None, "pendingReview": True}

        cells: dict[MilestoneCode, MilestoneCell] = {}
        total_paid = 0.0
        for m in (MilestoneCode.M1, MilestoneCode.M2, MilestoneCode.M3):
            inv = by_m.get(m.value, {})
            st = _to_display_status(inv, p)
            amt = float(inv.get("amount") or 0)
            if st == InvoiceDisplayStatus.PAID:
                total_paid += amt
            cells[m] = MilestoneCell(
                milestone=m,
                label=MILESTONE_LABEL[m],
                amount=amt,
                status=st,
                days_overdue=_days_overdue(inv.get("due_at")) if st == InvoiceDisplayStatus.OVERDUE else None,
                days_remaining=_days_remaining(inv.get("due_at")) if st == InvoiceDisplayStatus.DUE else None,
                invoice_id=str(inv["_id"]) if inv.get("_id") else None,
            )

        contracted_val = float(p["contracted_amount"]) if commercial_ok else 0.0
        balance = max(0.0, contracted_val - total_paid)

        rows.append(
            PortfolioProjectRow(
                project_id=pid,
                name=p["name"],
                client_name=p["client_name"],
                contracted_display=contracted_display,
                m1=cells[MilestoneCode.M1],
                m2=cells[MilestoneCode.M2],
                m3=cells[MilestoneCode.M3],
                total_paid=round(total_paid, 2),
                balance_due=round(balance, 2),
                currency=p.get("currency") or "USD",
            )
        )

    if project_ids:
        wanted = {str(x) for x in project_ids}
        rows = [r for r in rows if r.project_id in wanted]

    if milestone_status_filter:
        wanted = set(milestone_status_filter)

        def _row_matches_any_milestone(r: PortfolioProjectRow) -> bool:
            for c in (r.m1, r.m2, r.m3):
                if c.status in wanted:
                    return True
            return False

        rows = [r for r in rows if _row_matches_any_milestone(r)]

    # BILL-002: overdue projects first (default)
    def sort_key_overdue(r: PortfolioProjectRow) -> tuple:
        od = max(
            r.m1.days_overdue or 0,
            r.m2.days_overdue or 0,
            r.m3.days_overdue or 0,
        )
        has_overdue = (
            r.m1.status == InvoiceDisplayStatus.OVERDUE
            or r.m2.status == InvoiceDisplayStatus.OVERDUE
            or r.m3.status == InvoiceDisplayStatus.OVERDUE
        )
        due_min = min(
            [x for x in [r.m1.days_remaining, r.m2.days_remaining, r.m3.days_remaining] if x is not None]
            or [9999]
        )
        return (0 if has_overdue else 1, -od if has_overdue else due_min, r.name.lower())

    if sort_by == "project_name":
        rows.sort(key=lambda r: r.name.lower())
    elif sort_by == "contracted_desc":
        rows.sort(
            key=lambda r: float(r.contracted_display.get("value") or 0.0),
            reverse=True,
        )
    elif sort_by == "balance_desc":
        rows.sort(key=lambda r: r.balance_due, reverse=True)
    else:
        rows.sort(key=sort_key_overdue)

    cur = rows[0].currency if rows else "USD"
    tc = sum(
        float(r.contracted_display["value"])
        for r in rows
        if r.contracted_display.get("value") is not None
    )
    tp = sum(r.total_paid for r in rows)
    tb = sum(r.balance_due for r in rows)

    footer = PortfolioFooter(
        total_contracted=round(tc, 2),
        total_paid=round(tp, 2),
        total_balance=round(tb, 2),
        currency=cur,
    )
    return PortfolioResponse(projects=rows, footer=footer)


async def list_invoices(
    enterprise_id: str,
    *,
    project_id: Optional[str] = None,
    milestones: Optional[list[MilestoneCode]] = None,
    status_filter: Optional[list[InvoiceDisplayStatus]] = None,
    raised_from: Optional[datetime] = None,
    raised_to: Optional[datetime] = None,
) -> list[InvoiceListItem]:
    await sync_invoice_overdue(enterprise_id)
    bproj = get_billing_projects_collection()
    binv = get_billing_invoices_collection()
    q: dict[str, Any] = {"enterprise_id": enterprise_id}
    if project_id:
        q["project_id"] = project_id
    if milestones:
        q["milestone"] = {"$in": [m.value for m in milestones]}

    invs = await binv.find(q).to_list(2000)
    projects = {
        str(p["_id"]): p
        for p in await bproj.find({"enterprise_id": enterprise_id}).to_list(500)
    }

    out: list[InvoiceListItem] = []
    for inv in invs:
        pid = inv["project_id"]
        pr = projects.get(pid, {})
        st = _to_display_status(inv, pr)
        if status_filter and st not in status_filter:
            continue
        ms = MilestoneCode(inv["milestone"])
        out.append(
            InvoiceListItem(
                id=str(inv["_id"]),
                number=inv.get("invoice_number") or "—",
                project_id=pid,
                project_name=pr.get("name", "—"),
                milestone=ms,
                milestone_label=MILESTONE_LABEL[ms],
                amount=float(inv.get("amount") or 0),
                currency=inv.get("currency") or "USD",
                raised_at=inv.get("raised_at"),
                due_at=inv.get("due_at"),
                paid_at=inv.get("paid_at"),
                status=st,
                days_overdue=_days_overdue(inv.get("due_at")) if st == InvoiceDisplayStatus.OVERDUE else None,
                days_remaining=_days_remaining(inv.get("due_at")) if st == InvoiceDisplayStatus.DUE else None,
            )
        )

    if raised_from or raised_to:
        def _in_raised_range(x: InvoiceListItem) -> bool:
            ra = x.raised_at
            if ra is None:
                return False
            if raised_from and ra < raised_from:
                return False
            if raised_to and ra > raised_to:
                return False
            return True

        out = [x for x in out if _in_raised_range(x)]

    # INV-001 default sort
    def inv_sort_key(x: InvoiceListItem) -> tuple:
        if x.status == InvoiceDisplayStatus.OVERDUE:
            return (0, -(x.days_overdue or 0))
        if x.status == InvoiceDisplayStatus.DUE:
            return (1, x.days_remaining if x.days_remaining is not None else 9999)
        if x.status == InvoiceDisplayStatus.PENDING or x.status == InvoiceDisplayStatus.AWAITING_SIGNOFF:
            return (2, x.project_name.lower())
        if x.status == InvoiceDisplayStatus.PAID:
            ts = x.paid_at or datetime.min.replace(tzinfo=timezone.utc)
            return (3, -ts.timestamp())
        return (4, x.number)

    out.sort(key=inv_sort_key)
    return out


async def get_billing_settings(enterprise_id: str) -> BillingSettingsResponse:
    ent = await get_enterprises_collection().find_one({"_id": _oid(enterprise_id)})
    if not ent:
        raise HTTPException(status_code=404, detail="Enterprise not found.")
    b = ent.get("billing_settings") or {}
    email = (b.get("billing_contact_email") or ent.get("admin_email") or "").strip()
    if not email:
        email = "billing-pending@example.com"
    return BillingSettingsResponse(
        billing_contact_email=email,
        billing_contact_name=b.get("billing_contact_name", ""),
        billing_address_line1=b.get("billing_address_line1", ""),
        billing_address_line2=b.get("billing_address_line2"),
        city=b.get("city", ""),
        state_province=b.get("state_province", ""),
        postal_code=b.get("postal_code", ""),
        country=b.get("country", "IN"),
        gst_or_vat_number=b.get("gst_or_vat_number"),
        preferred_payment_method=b.get("preferred_payment_method", "bank_transfer_neft"),
        bank_account_last4=b.get("bank_account_last4"),
        bank_ifsc=b.get("bank_ifsc"),
    )


async def patch_billing_settings(enterprise_id: str, body: BillingSettingsUpdate) -> BillingSettingsResponse:
    ent_col = get_enterprises_collection()
    oid = _oid(enterprise_id)
    if not await ent_col.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail="Enterprise not found.")

    # BS-001..BS-003 basic validation
    if body.country == "IN":
        if not body.gst_or_vat_number or not str(body.gst_or_vat_number).strip():
            raise HTTPException(status_code=422, detail="GSTIN is required for India.")
        g = body.gst_or_vat_number.strip().upper()
        if len(g) != 15 or not g[:2].isdigit():
            raise HTTPException(status_code=422, detail="Invalid GSTIN format.")
    _bank_methods = frozenset({"bank_transfer_neft", "imps", "rtgs"})
    _is_bank = body.preferred_payment_method in _bank_methods or str(
        body.preferred_payment_method
    ).startswith("bank")
    if _is_bank:
        if not body.bank_account_last4:
            raise HTTPException(
                status_code=422,
                detail="Bank account number is required for this payment method.",
            )
        if not body.bank_account_last4.isdigit() or len(body.bank_account_last4) != 4:
            raise HTTPException(status_code=422, detail="Invalid bank account number format.")
        if body.country == "IN":
            if not body.bank_ifsc or not str(body.bank_ifsc).strip():
                raise HTTPException(
                    status_code=422,
                    detail="IFSC code is required for India bank transfers.",
                )
        if body.bank_ifsc:
            ifsc = body.bank_ifsc.strip().upper()
            if len(ifsc) != 11 or not ifsc[:4].isalpha():
                raise HTTPException(status_code=422, detail="Invalid IFSC code format.")

    doc = {
        "billing_contact_email": body.billing_contact_email.lower(),
        "billing_contact_name": body.billing_contact_name.strip(),
        "billing_address_line1": body.billing_address_line1.strip(),
        "billing_address_line2": (body.billing_address_line2 or "").strip() or None,
        "city": body.city.strip(),
        "state_province": body.state_province.strip(),
        "postal_code": body.postal_code.strip(),
        "country": body.country,
        "gst_or_vat_number": body.gst_or_vat_number.strip() if body.gst_or_vat_number else None,
        "preferred_payment_method": body.preferred_payment_method,
        "bank_account_last4": body.bank_account_last4,
        "bank_ifsc": body.bank_ifsc.strip().upper() if body.bank_ifsc else None,
    }
    now = _utc_now()
    await ent_col.update_one(
        {"_id": oid},
        {"$set": {"billing_settings": doc, "updated_at": now}},
    )
    return await get_billing_settings(enterprise_id)


async def admin_raise_invoice(invoice_id: str) -> AdminRaiseInvoiceResponse:
    """GlimmoraTeam Admin raises invoice (pending → due with dates)."""
    binv = get_billing_invoices_collection()
    bproj = get_billing_projects_collection()
    oid = _oid(invoice_id)
    inv = await binv.find_one({"_id": oid})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if inv.get("lifecycle") == "raised":
        raise HTTPException(status_code=400, detail="Invoice already raised.")
    pr = await bproj.find_one(
        {"_id": _oid(inv["project_id"]), "enterprise_id": inv["enterprise_id"]}
    )
    if not pr:
        raise HTTPException(status_code=404, detail="Project not found.")

    ms = MilestoneCode(inv["milestone"])
    if ms == MilestoneCode.M3 and not pr.get("uat_signoff_complete", False):
        raise HTTPException(
            status_code=400,
            detail="M3 cannot be raised until UAT sign-off is recorded on the project.",
        )
    if float(inv.get("amount") or 0) <= 0:
        raise HTTPException(status_code=400, detail="Contracted value not confirmed — cannot raise invoice.")

    number = await _next_invoice_number()
    now = _utc_now()
    if ms == MilestoneCode.M1:
        due = now
    else:
        due = now + timedelta(days=7)

    await binv.update_one(
        {"_id": oid},
        {
            "$set": {
                "invoice_number": number,
                "lifecycle": "raised",
                "payment_status": "due",
                "raised_at": now,
                "due_at": due,
                "updated_at": now,
            }
        },
    )
    return AdminRaiseInvoiceResponse(
        invoice_id=invoice_id,
        status=InvoiceDisplayStatus.DUE,
        raised_at=now,
        due_at=due,
    )


async def admin_confirm_payment(invoice_id: str) -> AdminConfirmPaymentResponse:
    """GlimmoraTeam Admin confirms bank receipt → PAID."""
    binv = get_billing_invoices_collection()
    oid = _oid(invoice_id)
    inv = await binv.find_one({"_id": oid})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if inv.get("lifecycle") != "raised":
        raise HTTPException(status_code=400, detail="Invoice is not in a payable state.")
    if inv.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="Already paid.")
    now = _utc_now()
    await binv.update_one(
        {"_id": oid},
        {"$set": {"payment_status": "paid", "paid_at": now, "updated_at": now}},
    )
    return AdminConfirmPaymentResponse(invoice_id=invoice_id, paid_at=now)


async def build_invoice_pdf_for_enterprise(invoice_id: str, enterprise_id: str) -> tuple[bytes, str]:
    """
    INV-002 — PDF for PAID / DUE / OVERDUE (raised invoices only).
    Returns PDF bytes and Content-Displacement filename (§10.2.4 pattern).
    """
    await sync_invoice_overdue(enterprise_id)
    binv = get_billing_invoices_collection()
    bproj = get_billing_projects_collection()
    ent_col = get_enterprises_collection()
    oid = _oid(invoice_id)
    inv = await binv.find_one({"_id": oid, "enterprise_id": enterprise_id})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if inv.get("lifecycle") != "raised" or not inv.get("invoice_number"):
        raise HTTPException(
            status_code=404,
            detail="Invoice PDF is available only after the invoice is raised.",
        )
    pr = await bproj.find_one(
        {"_id": _oid(inv["project_id"]), "enterprise_id": enterprise_id}
    )
    if not pr:
        raise HTTPException(status_code=404, detail="Project not found.")
    ms = MilestoneCode(inv["milestone"])
    ent = await ent_col.find_one({"_id": _oid(enterprise_id)})
    b = (ent or {}).get("billing_settings") or {}
    addr2 = (b.get("billing_address_line2") or "").strip()
    bill_to_lines = [
        (b.get("billing_contact_name") or "").strip(),
        (b.get("billing_address_line1") or "").strip(),
        addr2,
        f"{(b.get('city') or '').strip()}, {(b.get('state_province') or '').strip()} {(b.get('postal_code') or '').strip()}",
        (b.get("country") or "").strip(),
    ]
    pdf_bytes = billing_pdf.build_milestone_invoice_pdf(
        invoice_number=str(inv["invoice_number"]),
        project_name=str(pr.get("name", "")),
        milestone_label=MILESTONE_LABEL[ms],
        amount=float(inv.get("amount") or 0),
        currency=str(inv.get("currency") or "USD"),
        raised_at=inv.get("raised_at"),
        due_at=inv.get("due_at"),
        bill_to_lines=bill_to_lines,
        gst_or_vat=(b.get("gst_or_vat_number") or "").strip() or None,
    )
    m_n = {"m1": 1, "m2": 2, "m3": 3}[inv["milestone"]]
    fname = (
        f'{inv["invoice_number"]}-{billing_pdf.safe_filename_part(str(pr.get("name", "")))}-M{m_n}.pdf'
    )
    return pdf_bytes, fname


async def build_invoices_zip_for_enterprise(
    enterprise_id: str,
    *,
    raised_from: Optional[datetime] = None,
    raised_to: Optional[datetime] = None,
) -> tuple[bytes, str]:
    """§10.2.4 — one PDF per raised invoice in range (document retrieval only)."""
    items = await list_invoices(
        enterprise_id,
        raised_from=raised_from,
        raised_to=raised_to,
    )
    eligible = [
        i
        for i in items
        if i.raised_at is not None
        and i.status
        in (
            InvoiceDisplayStatus.PAID,
            InvoiceDisplayStatus.DUE,
            InvoiceDisplayStatus.OVERDUE,
        )
    ]
    if not eligible:
        raise HTTPException(
            status_code=404,
            detail="No raised invoices in the selected date range.",
        )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for it in eligible:
            pdf_bytes, inner_name = await build_invoice_pdf_for_enterprise(it.id, enterprise_id)
            zf.writestr(inner_name, pdf_bytes)
    buf.seek(0)
    tag = _utc_now().strftime("%Y%m%d")
    return buf.getvalue(), f"glimmora-invoices-{tag}.zip"

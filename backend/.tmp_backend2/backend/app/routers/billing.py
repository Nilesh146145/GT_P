"""
Billing API (FSD §10) — portfolio grid, invoices, settings; admin raise/confirm payment.
"""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from fastapi.responses import Response

from app.core.dependencies import (
    require_admin_or_platform_admin,
    require_enterprise_org_member,
)
from app.schemas.billing import (
    BillingSettingsUpdate,
    BulkInvoicePdfZipRequest,
    CreateBillingProjectRequest,
    InvoiceDisplayStatus,
    MilestoneCode,
)
from app.schemas.common import BaseResponse
from app.services import billing_service

router = APIRouter(prefix="/billing", tags=["Billing"])


def _parse_status_list(
    raw: Optional[str],
) -> Optional[list[InvoiceDisplayStatus]]:
    if not raw or not raw.strip():
        return None
    parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
    if not parts or parts == ["ALL"]:
        return None
    out: list[InvoiceDisplayStatus] = []
    for p in parts:
        try:
            out.append(InvoiceDisplayStatus(p))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid invoice status: {p}",
            ) from exc
    return out


def _parse_milestones(raw: Optional[str]) -> Optional[list[MilestoneCode]]:
    if not raw or not raw.strip():
        return None
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    if not parts or parts == ["all"]:
        return None
    out: list[MilestoneCode] = []
    for p in parts:
        try:
            out.append(MilestoneCode(p))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid milestone: {p} (use m1, m2, m3).",
            ) from exc
    return out


@router.get(
    "/portfolio",
    response_model=BaseResponse,
    summary="All Projects — portfolio payment grid",
)
async def get_portfolio(
    current_user: dict = Depends(require_enterprise_org_member),
    project_ids: Annotated[Optional[str], Query(alias="projectIds")] = None,
    milestone_status: Annotated[Optional[str], Query(alias="milestoneStatus")] = None,
    sort_by: Annotated[
        str,
        Query(
            alias="sortBy",
            description="overdue_first | project_name | contracted_desc | balance_desc",
        ),
    ] = "overdue_first",
):
    """One row per project with M1/M2/M3 cells and portfolio footer totals."""
    eid = str(current_user["enterprise_profile_id"])
    pids = [x.strip() for x in project_ids.split(",")] if project_ids else None
    if pids == [""]:
        pids = None
    ms = _parse_status_list(milestone_status)
    if sort_by not in (
        "overdue_first",
        "project_name",
        "contracted_desc",
        "balance_desc",
    ):
        raise HTTPException(status_code=422, detail="Invalid sortBy.")
    data = await billing_service.get_portfolio(
        eid,
        project_ids=pids,
        milestone_status_filter=ms,
        sort_by=sort_by,
    )
    return BaseResponse(
        message="Portfolio loaded.",
        data=data.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/snapshot",
    response_model=BaseResponse,
    summary="Financial Snapshot (dashboard)",
)
async def get_financial_snapshot(
    current_user: dict = Depends(require_enterprise_org_member),
):
    """Headline figures for the dashboard Financial Snapshot panel."""
    eid = str(current_user["enterprise_profile_id"])
    snap = await billing_service.get_financial_snapshot(eid)
    return BaseResponse(
        message="Financial snapshot loaded.",
        data=snap.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/invoices",
    response_model=BaseResponse,
    summary="All milestone invoices",
)
async def list_invoices(
    current_user: dict = Depends(require_enterprise_org_member),
    project_id: Annotated[Optional[str], Query(alias="projectId")] = None,
    milestones: Annotated[Optional[str], Query()] = None,
    invoice_status: Annotated[Optional[str], Query(alias="status")] = None,
    raised_from: Annotated[Optional[datetime], Query(alias="raisedFrom")] = None,
    raised_to: Annotated[Optional[datetime], Query(alias="raisedTo")] = None,
):
    """Document-level invoice list with default urgency ordering (INV-001)."""
    eid = str(current_user["enterprise_profile_id"])
    ms = _parse_milestones(milestones)
    st = _parse_status_list(invoice_status)
    items = await billing_service.list_invoices(
        eid,
        project_id=project_id,
        milestones=ms,
        status_filter=st,
        raised_from=raised_from,
        raised_to=raised_to,
    )
    return BaseResponse(
        message="Invoices loaded.",
        data=[i.model_dump(by_alias=True, mode="json") for i in items],
    )


@router.post(
    "/invoices/bulk-pdf-zip",
    summary="Bulk download raised invoices as ZIP (FSD §10.2.4)",
    response_class=Response,
    responses={
        200: {
            "content": {"application/zip": {}},
            "description": "ZIP of PDFs, one per raised invoice in range.",
        }
    },
)
async def bulk_invoice_pdf_zip(
    current_user: dict = Depends(require_enterprise_org_member),
    body: BulkInvoicePdfZipRequest = Body(..., examples=[{}]),
):
    """
    Document retrieval only — does not change payment status.

    Filters by **raised** date when ``raisedFrom`` / ``raisedTo`` are set; otherwise
    includes all raised invoices (PAID / DUE / OVERDUE).
    """
    eid = str(current_user["enterprise_profile_id"])
    zbytes, filename = await billing_service.build_invoices_zip_for_enterprise(
        eid,
        raised_from=body.raised_from,
        raised_to=body.raised_to,
    )
    return Response(
        content=zbytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/invoices/{invoice_id}/pdf",
    summary="Download single invoice PDF (INV-002)",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "GST-style milestone PDF",
        }
    },
)
async def download_invoice_pdf(
    invoice_id: str = Path(..., description="Mongo id of billing_invoices document"),
    current_user: dict = Depends(require_enterprise_org_member),
):
    """Available for PAID, DUE, and OVERDUE — not for PENDING / AWAITING_SIGNOFF."""
    eid = str(current_user["enterprise_profile_id"])
    pdf_bytes, filename = await billing_service.build_invoice_pdf_for_enterprise(
        invoice_id,
        eid,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/settings",
    response_model=BaseResponse,
    summary="Billing settings (read)",
)
async def get_billing_settings(
    current_user: dict = Depends(require_enterprise_org_member),
):
    eid = str(current_user["enterprise_profile_id"])
    s = await billing_service.get_billing_settings(eid)
    return BaseResponse(
        message="Billing settings loaded.",
        data=s.model_dump(by_alias=True, mode="json"),
    )


@router.patch(
    "/settings",
    response_model=BaseResponse,
    summary="Billing settings (update)",
)
async def patch_billing_settings(
    body: BillingSettingsUpdate,
    current_user: dict = Depends(require_enterprise_org_member),
):
    """§10.5 — enterprise billing identity (GST/IFSC validation per BS-001..BS-003)."""
    eid = str(current_user["enterprise_profile_id"])
    s = await billing_service.patch_billing_settings(eid, body)
    return BaseResponse(
        message="Billing settings saved.",
        data=s.model_dump(by_alias=True, mode="json"),
    )


@router.post(
    "/projects",
    response_model=BaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a billable project",
)
async def create_billing_project(
    body: CreateBillingProjectRequest,
    current_user: dict = Depends(require_enterprise_org_member),
):
    """
    Creates portfolio row + three placeholder invoices (M1/M2/M3).

    Used for onboarding and tests; production may also sync from wizard approvals.
    """
    eid = str(current_user["enterprise_profile_id"])
    created = await billing_service.create_billing_project(eid, body)
    return BaseResponse(
        message="Billing project registered.",
        data=created,
    )


@router.post(
    "/admin/invoices/{invoice_id}/raise",
    response_model=BaseResponse,
    summary="Admin: raise milestone invoice",
)
async def admin_raise_invoice(
    invoice_id: str = Path(..., description="Mongo id of billing_invoices document"),
    current_user: dict = Depends(require_admin_or_platform_admin),
):
    """GlimmoraTeam Admin issues PDF-backed invoice (lifecycle not_raised → raised)."""
    out = await billing_service.admin_raise_invoice(invoice_id)
    return BaseResponse(
        message="Invoice raised.",
        data=out.model_dump(by_alias=True, mode="json"),
    )


@router.post(
    "/admin/invoices/{invoice_id}/confirm-payment",
    response_model=BaseResponse,
    summary="Admin: confirm payment received",
)
async def admin_confirm_payment(
    invoice_id: str = Path(..., description="Mongo id of billing_invoices document"),
    current_user: dict = Depends(require_admin_or_platform_admin),
):
    """GlimmoraTeam Admin confirms bank receipt → PAID."""
    out = await billing_service.admin_confirm_payment(invoice_id)
    return BaseResponse(
        message="Payment confirmed.",
        data=out.model_dump(by_alias=True, mode="json"),
    )

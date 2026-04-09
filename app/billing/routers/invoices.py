from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.billing.dependencies import require_billing_user
from app.billing.schemas.invoice import CreateInvoiceRequest, UpdateInvoiceRequest
from app.billing.services import invoice_service, receipt_service
from app.schemas.common import BaseResponse

router = APIRouter()


@router.get("/invoices", response_model=BaseResponse)
async def list_invoices(
    status_value: str | None = Query(default=None, alias="status"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort_by: Literal["date", "amount", "status"] = Query(default="date"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    current_user: dict = Depends(require_billing_user),
) -> BaseResponse:
    items = await invoice_service.list_invoices(
        current_user,
        status_filter=status_value,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return BaseResponse(data=items)


@router.get("/invoices/{invoice_id}", response_model=BaseResponse)
async def get_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
    current_user: dict = Depends(require_billing_user),
) -> BaseResponse:
    data = await invoice_service.get_invoice(current_user, invoice_id)
    return BaseResponse(data=data)


@router.post("/invoices", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: CreateInvoiceRequest,
    current_user: dict = Depends(require_billing_user),
) -> BaseResponse:
    data = await invoice_service.create_invoice(current_user, payload)
    return BaseResponse(message="Invoice created.", data=data)


@router.patch("/invoices/{invoice_id}", response_model=BaseResponse)
async def patch_invoice(
    payload: UpdateInvoiceRequest,
    invoice_id: str = Path(..., description="Invoice ID"),
    current_user: dict = Depends(require_billing_user),
) -> BaseResponse:
    data = await invoice_service.update_invoice(current_user, invoice_id, payload)
    return BaseResponse(message="Invoice updated.", data=data)


@router.get(
    "/invoices/{invoice_id}/receipt",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def invoice_receipt(
    invoice_id: str = Path(..., description="Invoice ID"),
    format: Literal["pdf"] = Query(default="pdf"),
    current_user: dict = Depends(require_billing_user),
) -> Response:
    pdf_bytes, filename = await receipt_service.build_invoice_receipt_pdf(current_user, invoice_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


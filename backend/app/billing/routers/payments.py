from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, status

from app.billing.dependencies import require_billing_user
from app.billing.models.billing import PaymentMethod
from app.billing.schemas.payment import CreatePaymentRequest
from app.billing.services import payment_service
from app.schemas.common import BaseResponse

router = APIRouter()


@router.get("/payments", response_model=BaseResponse)
async def list_payments(
    status_value: str | None = Query(default=None, alias="status"),
    method: PaymentMethod | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: dict = Depends(require_billing_user),
) -> BaseResponse:
    items = await payment_service.list_payments(
        current_user,
        status_filter=status_value,
        method=method.value if method else None,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return BaseResponse(data=items)


@router.post("/payments", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: CreatePaymentRequest,
    current_user: dict = Depends(require_billing_user),
) -> BaseResponse:
    data = await payment_service.create_payment(current_user, payload)
    return BaseResponse(message="Payment recorded.", data=data)


@router.get("/payments/{payment_id}", response_model=BaseResponse)
async def get_payment(
    payment_id: str = Path(..., description="Payment ID"),
    current_user: dict = Depends(require_billing_user),
) -> BaseResponse:
    data = await payment_service.get_payment(current_user, payment_id)
    return BaseResponse(data=data)


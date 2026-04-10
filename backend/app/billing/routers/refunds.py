from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status

from app.billing.dependencies import require_billing_user
from app.billing.schemas.refund import CreateRefundRequest
from app.billing.services import refund_service
from app.schemas.common import BaseResponse

router = APIRouter()


@router.post("/refunds", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_refund(
    payload: CreateRefundRequest,
    current_user: dict = Depends(require_billing_user),
) -> BaseResponse:
    data = await refund_service.create_refund(current_user, payload)
    return BaseResponse(message="Refund recorded.", data=data)


@router.get("/refunds", response_model=BaseResponse)
async def list_refunds(current_user: dict = Depends(require_billing_user)) -> BaseResponse:
    items = await refund_service.list_refunds(current_user)
    return BaseResponse(data=items)


@router.get("/refunds/{refund_id}", response_model=BaseResponse)
async def get_refund(
    refund_id: str = Path(..., description="Refund ID"),
    current_user: dict = Depends(require_billing_user),
) -> BaseResponse:
    data = await refund_service.get_refund(current_user, refund_id)
    return BaseResponse(data=data)


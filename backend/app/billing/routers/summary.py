from __future__ import annotations

from fastapi import APIRouter, Depends

from app.billing.dependencies import require_billing_user
from app.billing.services import summary_service
from app.schemas.common import BaseResponse

router = APIRouter()


@router.get("/summary", response_model=BaseResponse)
async def get_summary(current_user: dict = Depends(require_billing_user)) -> BaseResponse:
    data = await summary_service.get_summary(current_user)
    return BaseResponse(data=data)

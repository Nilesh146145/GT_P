from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers.decomposition._dependencies import enterprise_profile_id, require_enterprise_user
from app.services.decomposition import summary_service

router = APIRouter()


@router.get("/{plan_id}/summary-panel")
async def get_summary_panel(
    plan_id: str,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await summary_service.get_summary_panel(eid, plan_id)

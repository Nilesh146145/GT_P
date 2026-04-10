from fastapi import APIRouter, Depends, Query

from app.routers.decomposition._dependencies import enterprise_profile_id, require_enterprise_user
from app.services.decomposition import plan_service

router = APIRouter(prefix="/plans/actions", tags=["Plan Actions"])


@router.post("/kickoff")
async def kickoff(
    plan_id: str = Query(..., description="Plan UUID (PENDING_KICKOFF)"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.kickoff(eid, plan_id)


@router.delete("/{plan_id}/withdraw", operation_id="withdraw_plan")
async def withdraw_plan(
    plan_id: str,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.withdraw_plan(eid, plan_id)

from fastapi import APIRouter, Depends

from app.routers.decomposition._dependencies import enterprise_profile_id, require_enterprise_user
from app.services.decomposition import revision_service

router = APIRouter()


@router.get("/{plan_id}/revised")
async def get_revised_plan(
    plan_id: str,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await revision_service.get_revised_plan(eid, plan_id)

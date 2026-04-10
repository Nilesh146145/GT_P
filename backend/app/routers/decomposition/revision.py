from fastapi import APIRouter, Depends, Path

from app.routers.decomposition._dependencies import enterprise_profile_id, require_enterprise_user
from app.services.decomposition import revision_service

router = APIRouter()


@router.get("/{plan_id}/revision-modal")
async def get_revision_modal(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await revision_service.get_revision_modal(eid, plan_id)

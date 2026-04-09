from fastapi import APIRouter, Depends

from app.routers.decomposition._dependencies import enterprise_profile_id, require_enterprise_user
from app.services.decomposition import revision_service

router = APIRouter()


@router.get("/{plan_id}/revisions/{revision_id}")
async def get_revision_detail(
    plan_id: str,
    revision_id: int,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await revision_service.get_revision_detail(eid, plan_id, revision_id)

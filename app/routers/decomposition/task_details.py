from fastapi import APIRouter, Depends

from app.routers.decomposition._dependencies import enterprise_profile_id, require_enterprise_user
from app.services.decomposition import task_service

router = APIRouter()


@router.get("/{plan_id}/tasks/{task_id}/detail")
async def get_task_detail(
    plan_id: str,
    task_id: int,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await task_service.get_task_detail(eid, plan_id, task_id)


@router.post("/{plan_id}/tasks/{task_id}/flag")
async def flag_task(
    plan_id: str,
    task_id: int,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await task_service.flag_task(eid, plan_id, task_id)

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers.decomposition._dependencies import enterprise_profile_id, require_enterprise_user
from app.services.decomposition import task_service

router = APIRouter()


@router.get("/{plan_id}/tasks")
async def get_tasks(
    plan_id: str,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await task_service.get_tasks(eid, plan_id)


@router.get("/{plan_id}/tasks/query")
async def query_tasks(
    plan_id: str,
    milestone: str | None = None,
    sort_by: str | None = "id",
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await task_service.query_tasks(eid, plan_id, milestone=milestone, sort_by=sort_by)


@router.get("/{plan_id}/tasks/{task_id}")
async def get_task(
    plan_id: str,
    task_id: int,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await task_service.get_task(eid, plan_id, task_id)


@router.get("/{plan_id}/milestones")
async def get_milestones(
    plan_id: str,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await task_service.get_milestones(eid, plan_id)


@router.get("/{plan_id}/critical-path")
async def critical_tasks(
    plan_id: str,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await task_service.critical_tasks(eid, plan_id)

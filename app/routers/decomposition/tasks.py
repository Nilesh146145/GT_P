from fastapi import APIRouter

from app.services.decomposition import task_service

router = APIRouter()


@router.get("/{plan_id}/tasks")
def get_tasks(plan_id: int):
    return task_service.get_tasks(plan_id)


@router.get("/{plan_id}/tasks/query")
def query_tasks(plan_id: int, milestone: str | None = None, sort_by: str | None = "id"):
    return task_service.query_tasks(plan_id, milestone=milestone, sort_by=sort_by)


@router.get("/{plan_id}/tasks/{task_id}")
def get_task(plan_id: int, task_id: int):
    return task_service.get_task(plan_id, task_id)


@router.get("/{plan_id}/milestones")
def get_milestones(plan_id: int):
    return task_service.get_milestones(plan_id)


@router.get("/{plan_id}/critical-path")
def critical_tasks(plan_id: int):
    return task_service.critical_tasks(plan_id)

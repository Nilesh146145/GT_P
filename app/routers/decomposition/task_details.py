from fastapi import APIRouter

from app.services.decomposition import task_service

router = APIRouter()


@router.get("/{plan_id}/tasks/{task_id}/detail")
def get_task_detail(plan_id: int, task_id: int):
    return task_service.get_task_detail(plan_id, task_id)


@router.post("/{plan_id}/tasks/{task_id}/flag")
def flag_task(plan_id: int, task_id: int):
    return task_service.flag_task(plan_id, task_id)

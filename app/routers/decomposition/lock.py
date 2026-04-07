from fastapi import APIRouter

from app.services.decomposition import plan_service

router = APIRouter()


@router.post("/{plan_id}/lock")
def lock_plan(plan_id: int):
    return plan_service.lock_plan_action(plan_id)


@router.get("/{plan_id}/status")
def get_plan_status(plan_id: int):
    return plan_service.get_lock_status(plan_id)

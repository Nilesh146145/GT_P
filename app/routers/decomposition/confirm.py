from fastapi import APIRouter

from app.services.decomposition import plan_service

router = APIRouter()


@router.post("/{plan_id}/confirm", operation_id="confirm_plan_action")
def confirm_plan(plan_id: int):
    return plan_service.confirm_plan_action(plan_id)

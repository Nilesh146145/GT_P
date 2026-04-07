from fastapi import APIRouter

from app.services.decomposition import plan_service

router = APIRouter(prefix="/plans/actions", tags=["Plan Actions"])


@router.post("/kickoff")
def kickoff(plan_id: str):
    return plan_service.kickoff(plan_id)


@router.delete("/{plan_id}/withdraw", operation_id="withdraw_plan")
def withdraw_plan(plan_id: str):
    return plan_service.withdraw_plan(plan_id)

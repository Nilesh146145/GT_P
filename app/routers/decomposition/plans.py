from fastapi import APIRouter, Body, Path

from app.schemas.decomposition.plans import (
    ConfirmPlanRequest,
    LockPlanRequest,
    PlanResponse,
    PlanStatusResponse,
    RevisionRequest,
)
from app.services.decomposition import plan_service

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.get("", summary="List all plans (dashboard overview)", response_model=list[PlanStatusResponse])
def list_plans():
    return plan_service.list_plans()


@router.get(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Fetch full plan for dashboard review",
)
def get_plan(plan_id: str = Path(..., description="Unique plan ID, e.g. PLAN-001")):
    return plan_service.get_plan(plan_id)


@router.get(
    "/{plan_id}/status",
    response_model=PlanStatusResponse,
    summary="Get current status of a plan",
)
def get_plan_status(plan_id: str = Path(..., description="Unique plan ID")):
    return plan_service.get_plan_status(plan_id)


@router.post("/{plan_id}/confirm", summary="Enterprise confirms the plan")
def confirm_plan(
    plan_id: str = Path(..., description="Unique plan ID"),
    body: ConfirmPlanRequest = Body(...),
):
    return plan_service.confirm_plan(plan_id, body)


@router.post("/{plan_id}/request-revision", summary="Enterprise requests a plan revision")
def request_revision(
    plan_id: str = Path(..., description="Unique plan ID"),
    body: RevisionRequest = Body(...),
):
    return plan_service.request_plan_revision(plan_id, body)


@router.post("/{plan_id}/lock", summary="Lock the plan when first contributor accepts")
def lock_plan(
    plan_id: str = Path(..., description="Unique plan ID"),
    body: LockPlanRequest = Body(...),
):
    return plan_service.lock_plan(plan_id, body)


@router.get("/{plan_id}/revision")
def get_revision(plan_id: int):
    return plan_service.get_revision(plan_id)


@router.post("/{plan_id}/revision")
def increase_revision(plan_id: int):
    return plan_service.increase_revision(plan_id)


@router.get("/{plan_id}/summary")
def get_summary(plan_id: int):
    return plan_service.get_summary(plan_id)


@router.post("/{plan_id}/request-revision")
def request_revision_status(plan_id: int):
    return plan_service.request_plan_revision_status(plan_id)


@router.get("/{plan_id}/status")
def get_status(plan_id: int):
    return plan_service.get_status(plan_id)


@router.get("/{plan_id}/checklist-status")
def get_checklist(plan_id: int):
    return plan_service.get_checklist_status(plan_id)


@router.post("/{plan_id}/confirm")
def confirm_plan_status(plan_id: int):
    return plan_service.confirm_plan_status(plan_id)

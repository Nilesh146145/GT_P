from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Path

from app.models.decomposition import ConfirmPlanRequest, CreateDecompositionPlanRequest, LockPlanRequest, RevisionRequest
from app.routers.decomposition._dependencies import enterprise_profile_id, require_enterprise_user
from app.schemas.decomposition.plans import (
    PlanResponse,
    PlanStatusResponse,
    RevisionCounterResponse,
    SummaryResponse,
)
from app.services.decomposition import plan_service

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.post("", summary="Create plan (PENDING_KICKOFF until kickoff releases it)")
async def create_plan(
    body: CreateDecompositionPlanRequest = Body(...),
    current_user: dict = Depends(require_enterprise_user),
):
    return await plan_service.create_plan(current_user, body)


@router.get("", summary="List all plans (dashboard overview)", response_model=list[PlanStatusResponse])
async def list_plans(current_user: dict = Depends(require_enterprise_user)):
    return await plan_service.list_plans_for_enterprise(current_user)


@router.get(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Fetch full plan for dashboard review",
)
async def get_plan(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.get_plan(eid, plan_id)


@router.get(
    "/{plan_id}/status",
    response_model=PlanStatusResponse,
    summary="Get current status of a plan",
)
async def get_plan_status(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.get_plan_status(eid, plan_id)


@router.post("/{plan_id}/confirm", summary="Enterprise confirms the plan")
async def confirm_plan(
    plan_id: str = Path(..., description="Plan UUID"),
    body: ConfirmPlanRequest = Body(...),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.confirm_plan(eid, plan_id, body)


@router.post("/{plan_id}/request-revision", summary="Enterprise requests a plan revision")
async def request_revision(
    plan_id: str = Path(..., description="Plan UUID"),
    body: RevisionRequest = Body(...),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.request_plan_revision(eid, plan_id, body)


@router.post("/{plan_id}/lock", summary="Lock the plan when first contributor accepts")
async def lock_plan(
    plan_id: str = Path(..., description="Plan UUID"),
    body: LockPlanRequest = Body(...),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.lock_plan(eid, plan_id, body)


@router.get("/{plan_id}/revision", response_model=RevisionCounterResponse)
async def get_revision(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.get_revision(eid, plan_id)


@router.get("/{plan_id}/summary", response_model=SummaryResponse)
async def get_summary(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.get_summary(eid, plan_id)


@router.get("/{plan_id}/state", summary="Raw plan state key (legacy clients)")
async def get_state(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.get_status(eid, plan_id)


@router.get("/{plan_id}/checklist-status", summary="Review checklist (item1–item3)")
async def get_checklist_status(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.get_checklist_status(eid, plan_id)


@router.post("/{plan_id}/confirm-legacy", summary="Confirm without body (uses server checklist only)")
async def confirm_plan_status(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await plan_service.confirm_plan_status(eid, plan_id)

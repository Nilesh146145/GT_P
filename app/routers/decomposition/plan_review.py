from fastapi import APIRouter, Body, Depends, Path

from app.models.decomposition import (
    ChecklistUpdateRequest,
    ChecklistUpdateResponse,
    PlanReviewPageResponse,
)
from app.routers.decomposition._dependencies import enterprise_profile_id, require_enterprise_user
from app.services.decomposition import checklist_service, revision_service, summary_service

router = APIRouter(prefix="/plans", tags=["Plan Review Page"])


@router.get("/{plan_id}/review", response_model=PlanReviewPageResponse, summary="Load full Plan Review Page")
async def get_plan_review_page(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await revision_service.get_plan_review_page(eid, plan_id)


@router.get("/{plan_id}/review/checklist", summary="Get review checklist state")
async def get_checklist(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await checklist_service.get_review_checklist(eid, plan_id)


@router.patch(
    "/{plan_id}/review/checklist",
    response_model=ChecklistUpdateResponse,
    summary="Check or uncheck a review checklist item",
)
async def update_checklist_item(
    plan_id: str = Path(..., description="Plan UUID"),
    body: ChecklistUpdateRequest = Body(...),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await checklist_service.update_review_checklist_item(
        eid,
        plan_id,
        item_id=body.item_id,
        is_checked=body.is_checked,
        updated_by=body.updated_by,
    )


@router.get("/{plan_id}/review/summary", summary="Get plan summary strip data")
async def get_plan_summary(
    plan_id: str = Path(..., description="Plan UUID"),
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await summary_service.get_plan_summary(eid, plan_id)

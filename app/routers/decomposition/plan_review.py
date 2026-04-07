from fastapi import APIRouter, Body, Path

from app.schemas.decomposition.checklist import ChecklistUpdateRequest, ChecklistUpdateResponse
from app.schemas.decomposition.revision import PlanReviewPageResponse
from app.services.decomposition import checklist_service, revision_service, summary_service

router = APIRouter(prefix="/plans", tags=["Plan Review Page"])


@router.get("/{plan_id}/review", response_model=PlanReviewPageResponse, summary="Load full Plan Review Page")
def get_plan_review_page(plan_id: str = Path(..., description="Unique plan ID")):
    return revision_service.get_plan_review_page(plan_id)


@router.get("/{plan_id}/review/checklist", summary="Get review checklist state")
def get_checklist(plan_id: str = Path(..., description="Unique plan ID")):
    return checklist_service.get_review_checklist(plan_id)


@router.patch(
    "/{plan_id}/review/checklist",
    response_model=ChecklistUpdateResponse,
    summary="Check or uncheck a review checklist item",
)
def update_checklist_item(
    plan_id: str = Path(..., description="Unique plan ID"),
    body: ChecklistUpdateRequest = Body(...),
):
    return checklist_service.update_review_checklist_item(
        plan_id=plan_id,
        item_id=body.item_id,
        is_checked=body.is_checked,
        updated_by=body.updated_by,
    )


@router.get("/{plan_id}/review/summary", summary="Get plan summary strip data")
def get_plan_summary(plan_id: str = Path(..., description="Unique plan ID")):
    return summary_service.get_plan_summary(plan_id)

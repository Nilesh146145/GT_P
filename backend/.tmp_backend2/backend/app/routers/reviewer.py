"""
Reviewer Router — dashboard, assigned projects, evidence recommendations.

All business routes require an active reviewer: ``check_reviewer_password_changed`` (no temp password) then
``require_active_reviewer`` (role + MFA). Login alone is insufficient without MFA enrollment for reviewers.
"""

from fastapi import APIRouter, Depends, Path

from app.core.dependencies import require_active_reviewer
from app.schemas.common import BaseResponse
from app.schemas.reviewer import EvidenceRecommendRequest, UpdateReviewerAssignmentStatusRequest
from app.services import reviewer_service

router = APIRouter(prefix="/reviewer", tags=["Reviewer"])


@router.get(
    "/dashboard",
    response_model=BaseResponse,
    summary="Reviewer dashboard (counts from MongoDB)",
)
async def reviewer_dashboard(
    current_user: dict = Depends(require_active_reviewer),
) -> BaseResponse:
    """Open assignments and pending evidence-review tasks for the authenticated reviewer."""
    data = await reviewer_service.get_dashboard(current_user["id"])
    return BaseResponse(message="Reviewer dashboard", data=data)


@router.get(
    "/projects",
    response_model=BaseResponse,
    summary="List projects assigned to this reviewer",
)
async def reviewer_projects(
    current_user: dict = Depends(require_active_reviewer),
) -> BaseResponse:
    """Assignment queue for this reviewer (newest first)."""
    items = await reviewer_service.list_assigned_projects(current_user["id"])
    return BaseResponse(data=items)


@router.patch(
    "/assignments/{assignment_id}",
    response_model=BaseResponse,
    summary="Update assignment status (reviewer)",
)
async def patch_reviewer_assignment(
    assignment_id: str,
    body: UpdateReviewerAssignmentStatusRequest,
    current_user: dict = Depends(require_active_reviewer),
) -> BaseResponse:
    """
    Move a queue item to ``in_progress`` or ``completed`` (project/other tasks).

    Evidence-review tasks: only ``pending`` → ``in_progress`` here; finish with
    ``POST /reviewer/evidence/{evidence_id}/recommend``.
    """
    data = await reviewer_service.update_assignment_status(
        current_user["id"],
        assignment_id,
        body,
    )
    return BaseResponse(message="Assignment updated.", data=data)


@router.post(
    "/evidence/{evidence_id}/recommend",
    response_model=BaseResponse,
    summary="Submit evidence pack recommendation",
)
async def recommend_evidence(
    body: EvidenceRecommendRequest,
    evidence_id: str = Path(..., description="Evidence pack or artifact ID"),
    current_user: dict = Depends(require_active_reviewer),
) -> BaseResponse:
    """Persist ACCEPT/REWORK with score and comment; completes matching evidence_review assignments."""
    result = await reviewer_service.submit_evidence_recommendation(
        evidence_id,
        body,
        current_user["id"],
    )
    return BaseResponse(
        message="Evidence recommendation recorded.",
        data=result,
    )

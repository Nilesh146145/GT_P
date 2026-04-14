from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.dependencies.reviewer import require_reviewer_user
from app.schemas.common import BaseResponse
from app.schemas.reviewer.assignment import UpdateReviewerAssignmentStatusRequest
from app.schemas.reviewer.evidence import EvidenceRecommendRequest
from app.services.reviewer import assignment_service, dashboard_service, evidence_service

router = APIRouter(prefix="/reviewer", tags=["Reviewer"])


@router.get("/dashboard", response_model=BaseResponse)
async def reviewer_dashboard(current_user: dict = Depends(require_reviewer_user)) -> BaseResponse:
    data = await dashboard_service.get_dashboard(current_user["id"])
    return BaseResponse(message="Reviewer dashboard", data=data)


@router.get("/projects", response_model=BaseResponse)
async def reviewer_projects(current_user: dict = Depends(require_reviewer_user)) -> BaseResponse:
    items = await assignment_service.list_assignments(current_user["id"])
    return BaseResponse(data=items)


@router.patch("/assignments/{assignment_id}", response_model=BaseResponse)
async def patch_reviewer_assignment(
    assignment_id: str,
    body: UpdateReviewerAssignmentStatusRequest,
    current_user: dict = Depends(require_reviewer_user),
) -> BaseResponse:
    data = await assignment_service.update_assignment_status(current_user["id"], assignment_id, body)
    return BaseResponse(message="Assignment updated.", data=data)


@router.post("/evidence/{evidence_id}/recommend", response_model=BaseResponse)
async def recommend_evidence(
    body: EvidenceRecommendRequest,
    evidence_id: str = Path(..., description="Evidence pack or artifact ID"),
    current_user: dict = Depends(require_reviewer_user),
) -> BaseResponse:
    result = await evidence_service.recommend_evidence(evidence_id, body, current_user["id"])
    return BaseResponse(message="Evidence recommendation recorded.", data=result)


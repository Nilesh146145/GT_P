from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status

from app.core.security import get_current_user
from app.dependencies.reviewer import require_reviewer_admin_user
from app.schemas.common import BaseResponse
from app.schemas.reviewer.assignment import CreateReviewerAssignmentRequest
from app.schemas.reviewer.reviewer_user import CreateReviewerRequest, CreateReviewerUserApiResponse
from app.services.reviewer import assignment_service, reviewer_auth_service, reviewer_user_service

router = APIRouter(prefix="/users", tags=["Users & Enterprise"])


@router.post("", response_model=CreateReviewerUserApiResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateReviewerRequest,
    current_user: dict = Depends(require_reviewer_admin_user),
) -> CreateReviewerUserApiResponse:
    created = await reviewer_user_service.create_reviewer_user(payload, current_user)
    return CreateReviewerUserApiResponse(
        message="Reviewer created successfully.",
        data=created,
    )


@router.get("/reviewers/{reviewer_user_id}/assignments", response_model=BaseResponse)
async def list_reviewer_assignments(
    reviewer_user_id: str = Path(..., description="Reviewer user ID"),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    reviewer_auth_service.ensure_assignment_access(current_user, reviewer_user_id)
    items = await assignment_service.list_assignments(reviewer_user_id)
    return BaseResponse(data=items)


@router.post(
    "/reviewers/{reviewer_user_id}/assignments",
    response_model=BaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reviewer_assignment(
    payload: CreateReviewerAssignmentRequest,
    reviewer_user_id: str = Path(..., description="Reviewer user ID"),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    reviewer_auth_service.ensure_assignment_access(current_user, reviewer_user_id)
    data = await assignment_service.create_assignment(
        reviewer_user_id,
        payload,
        str(current_user.get("id") or current_user.get("_id")),
    )
    return BaseResponse(message="Assignment created.", data=data)


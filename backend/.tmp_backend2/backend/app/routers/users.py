"""
Users Router — enterprise user management and user picker support.
The user picker is used in Step 9 for designating Business Owner Approver,
Final Approver, Legal Reviewer, and Security Reviewer.
"""

from fastapi import APIRouter, Depends, Query, Path
from bson import ObjectId

from app.core.dependencies import (
    ensure_can_manage_reviewer_assignments,
    require_enterprise_org_admin_or_platform,
)
from app.core.security import get_current_user
from app.core.database import get_users_collection
from app.schemas.common import BaseResponse
from app.schemas.reviewer import CreateReviewerAssignmentRequest
from app.schemas.users import CreateReviewerRequest, CreateReviewerUserApiResponse
from app.services import reviewer_service, user_service

router = APIRouter(prefix="/users", tags=["Users & Enterprise"])


@router.post(
    "",
    response_model=CreateReviewerUserApiResponse,
    status_code=201,
    summary="Create a reviewer user (enterprise or platform admin)",
    response_description=(
        "Full FSD profile under `data` plus one-time `temporaryPassword`. "
        "In Swagger, expand **CreateReviewerUserApiResponse** → **data** to see all fields."
    ),
)
async def create_user(
    payload: CreateReviewerRequest,
    current_user: dict = Depends(require_enterprise_org_admin_or_platform),
) -> CreateReviewerUserApiResponse:
    """
    Enterprise org admin or platform admin provisions a reviewer (FSD profile + system ``reviewer`` role).

    **Request:** identity and org profile — ``email``, ``firstName``, ``lastName``,
    ``role`` (job title), ``designation``, ``department``, ``username``,
    ``language``, ``timeZone``, and ``status`` — one of **ACTIVE**, **INVITED**, **EXPIRED**
    (defaults to **INVITED**). **EXPIRED** sets the account so it cannot sign in.
    Do **not** send a password; the API returns ``data.temporaryPassword`` once.

    **Response:** echoes profile fields; ``role`` is always the system value ``reviewer``;
    job title is ``jobTitle``; lifecycle is ``status`` (ACTIVE/INVITED/EXPIRED).
    """
    _ = current_user
    created = await user_service.create_reviewer_by_admin(payload)
    return CreateReviewerUserApiResponse(
        message="Reviewer created successfully.",
        data=created,
    )


@router.get("/search", response_model=BaseResponse,
            summary="Search users for approver picker (Step 9)")
async def search_users(
    q: str = Query(..., min_length=2, description="Name or email search query"),
    organisation: str = Query(None, description="Filter by organisation"),
    current_user: dict = Depends(get_current_user)
):
    """
    Used in Step 9 user picker for designating:
    - Business Owner Approver
    - Final Approver
    - Legal/Compliance Reviewer (optional)
    - Security Reviewer (optional)

    Returns user ID, full name, email, and organisation.
    Passwords are never returned.
    """
    col = get_users_collection()
    query: dict = {
        "$or": [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]
    }
    if organisation:
        query["organisation"] = {"$regex": organisation, "$options": "i"}

    cursor = col.find(query, {"hashed_password": 0}).limit(20)
    users = []
    async for u in cursor:
        u["id"] = str(u.pop("_id"))
        users.append(u)

    return BaseResponse(data=users)


@router.get(
    "/reviewers/{reviewer_user_id}/assignments",
    response_model=BaseResponse,
    summary="List a reviewer's assignments (admin or that reviewer)",
)
async def list_reviewer_assignments(
    reviewer_user_id: str = Path(..., description="Reviewer user ID"),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """Same shape as ``GET /reviewer/projects`` for the given reviewer user."""
    ensure_can_manage_reviewer_assignments(current_user, reviewer_user_id)
    items = await reviewer_service.list_assigned_projects(reviewer_user_id)
    return BaseResponse(data=items)


@router.post(
    "/reviewers/{reviewer_user_id}/assignments",
    response_model=BaseResponse,
    status_code=201,
    summary="Assign a task to a reviewer (admin) or add to your own queue (reviewer)",
)
async def create_reviewer_assignment(
    payload: CreateReviewerAssignmentRequest,
    reviewer_user_id: str = Path(..., description="Reviewer user ID"),
    current_user: dict = Depends(get_current_user),
) -> BaseResponse:
    """
    Creates a queue row for the reviewer dashboard and ``GET /reviewer/projects``.

    Enterprise/platform admins may target any reviewer user id. A logged-in **reviewer**
    may only use their **own** id (from ``GET /auth/me``), after password + MFA setup.

    ``task_kind`` ``evidence_review`` with ``related_id`` set to the evidence pack id ties
    the row to ``POST /reviewer/evidence/{evidence_id}/recommend`` completion.
    """
    ensure_can_manage_reviewer_assignments(current_user, reviewer_user_id)
    data = await reviewer_service.create_assignment(
        reviewer_user_id,
        payload,
        str(current_user["id"]),
    )
    return BaseResponse(message="Assignment created.", data=data)


@router.get("/{user_id}", response_model=BaseResponse,
            summary="Get user profile by ID")
async def get_user(
    user_id: str = Path(..., description="User ID"),
    current_user: dict = Depends(get_current_user)
):
    """Returns public profile for a user ID. Used to display approver names throughout the platform."""
    col = get_users_collection()
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid user ID.")

    user = await col.find_one({"_id": obj_id}, {"hashed_password": 0})
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found.")

    user["id"] = str(user.pop("_id"))
    return BaseResponse(data=user)

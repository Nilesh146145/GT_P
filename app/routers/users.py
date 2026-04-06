"""
Users Router — enterprise user management and user picker support.
The user picker is used in Step 9 for designating Business Owner Approver,
Final Approver, Legal Reviewer, and Security Reviewer.
"""

from fastapi import APIRouter, Depends, Query, Path
from bson import ObjectId

from app.core.security import get_current_user
from app.core.database import get_users_collection
from app.schemas.common import BaseResponse

router = APIRouter(prefix="/users", tags=["Users & Enterprise"])


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

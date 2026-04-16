"""
Users Router — enterprise user management and user picker support.
The user picker is used in Step 9 for designating Business Owner Approver,
Final Approver, Legal Reviewer, and Security Reviewer.
"""
from __future__ import annotations


from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from bson import ObjectId

from app.core.security import get_current_user
from app.core.database import get_users_collection
from app.schemas.common import BaseResponse
from app.schemas.profile import UpdateMyProfileRequest
from app.services import profile_service

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


@router.get("/me/profile", response_model=BaseResponse, summary="Get current user profile")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """Returns role-aware profile details for the current authenticated user."""
    return BaseResponse(data=await profile_service.get_my_profile(current_user))


@router.put("/me/profile", response_model=BaseResponse, summary="Update current user profile")
async def update_my_profile(
    payload: UpdateMyProfileRequest,
    current_user: dict = Depends(get_current_user),
):
    """Updates current user's editable profile fields without changing auth/session flows."""
    data = await profile_service.update_my_profile(current_user, payload)
    return BaseResponse(message="Profile updated successfully.", data=data)


@router.post("/me/profile-picture", response_model=BaseResponse, summary="Upload profile picture")
async def upload_profile_picture(
    file: UploadFile = File(..., description="JPEG/PNG/WEBP image up to 2 MB"),
    current_user: dict = Depends(get_current_user),
):
    """Stores user profile picture as a data URL for immediate frontend rendering."""
    data = await profile_service.save_profile_picture(current_user, file)
    return BaseResponse(message="Profile picture updated successfully.", data=data)


@router.delete("/me/profile-picture", response_model=BaseResponse, summary="Remove profile picture")
async def delete_profile_picture(current_user: dict = Depends(get_current_user)):
    """Clears the current user's profile picture."""
    data = await profile_service.remove_profile_picture(current_user)
    return BaseResponse(message="Profile picture removed successfully.", data=data)

"""
Profile service for read/update profile and profile picture flows.
"""

import base64
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, UploadFile, status

from app.core.database import get_enterprises_collection, get_users_collection
from app.schemas.enterprise_auth import EnterpriseCompanyProfile
from app.schemas.profile import UpdateMyProfileRequest

ALLOWED_PROFILE_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PROFILE_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _public_user_profile(user: dict, enterprise_profile: EnterpriseCompanyProfile | None) -> dict:
    contributor_profile = user.get("contributor_profile")
    if isinstance(contributor_profile, dict) and contributor_profile.get("date_of_birth"):
        contributor_profile = dict(contributor_profile)
        contributor_profile["date_of_birth"] = str(contributor_profile["date_of_birth"])

    data = {
        "id": str(user["_id"]),
        "email": user.get("email"),
        "role": user.get("role"),
        "firstName": user.get("first_name", ""),
        "lastName": user.get("last_name", ""),
        "fullName": user.get("full_name", ""),
        "phoneNumber": user.get("phone"),
        "profileImageUrl": user.get("profile_image_data_url"),
        "contributorProfile": contributor_profile if user.get("role") == "contributor" else None,
        "enterpriseProfile": None,
    }
    if enterprise_profile is not None:
        data["enterpriseProfile"] = enterprise_profile.model_dump(by_alias=True)
    return data


async def get_my_profile(current_user: dict) -> dict:
    enterprise_profile = None
    if current_user.get("role") == "enterprise" and current_user.get("enterprise_profile_id"):
        try:
            enterprise_oid = ObjectId(str(current_user["enterprise_profile_id"]))
        except InvalidId:
            enterprise_oid = None
        enterprise = await get_enterprises_collection().find_one({"_id": enterprise_oid}) if enterprise_oid else None
        if enterprise:
            enterprise_profile = EnterpriseCompanyProfile(
                enterprise_profile_id=str(enterprise["_id"]),
                org_name=enterprise.get("org_name") or "",
                org_type=enterprise.get("org_type") or "",
                org_type_other=enterprise.get("org_type_other"),
                industry=enterprise.get("industry") or "",
                industry_other=enterprise.get("industry_other"),
                company_size=enterprise.get("company_size") or "",
                website=enterprise.get("website"),
                hq_country=enterprise.get("hq_country"),
                hq_city=enterprise.get("hq_city"),
                admin_title=enterprise.get("admin_title") or "",
                admin_dept=enterprise.get("admin_dept"),
                incorporation_country=enterprise.get("incorporation_country"),
            )
    return _public_user_profile(current_user, enterprise_profile)


async def update_my_profile(current_user: dict, payload: UpdateMyProfileRequest) -> dict:
    role = str(current_user.get("role") or "").strip().lower()
    user_updates: dict[str, object] = {}
    now = _now_utc()

    if payload.first_name is not None:
        user_updates["first_name"] = payload.first_name
    if payload.last_name is not None:
        user_updates["last_name"] = payload.last_name
    if payload.phone is not None:
        user_updates["phone"] = payload.phone

    if payload.contributor_profile is not None:
        if role != "contributor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only contributor users can update contributorProfile.",
            )
        cp_updates = payload.contributor_profile.model_dump(exclude_none=True)
        if "date_of_birth" in cp_updates and cp_updates["date_of_birth"] is not None:
            cp_updates["date_of_birth"] = cp_updates["date_of_birth"].isoformat()
        for key, value in cp_updates.items():
            user_updates[f"contributor_profile.{key}"] = value

    if payload.enterprise_profile is not None:
        if role != "enterprise":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only enterprise users can update enterpriseProfile.",
            )
        enterprise_profile_id = current_user.get("enterprise_profile_id")
        if not enterprise_profile_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enterprise profile not linked.")
        try:
            enterprise_oid = ObjectId(str(enterprise_profile_id))
        except InvalidId as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid enterprise profile ID.") from exc

        enterprise_updates = payload.enterprise_profile.model_dump(exclude_none=True)
        if enterprise_updates:
            enterprise_updates["updated_at"] = now
            result = await get_enterprises_collection().update_one(
                {"_id": enterprise_oid},
                {"$set": enterprise_updates},
            )
            if result.matched_count == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enterprise profile not found.")

    if user_updates:
        effective_first = user_updates.get("first_name", current_user.get("first_name", ""))
        effective_last = user_updates.get("last_name", current_user.get("last_name", ""))
        user_updates["full_name"] = f"{effective_first} {effective_last}".strip()
        user_updates["updated_at"] = now
        await get_users_collection().update_one({"_id": current_user["_id"]}, {"$set": user_updates})

    refreshed_user = await get_users_collection().find_one({"_id": current_user["_id"]})
    if refreshed_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return await get_my_profile(refreshed_user)


async def save_profile_picture(current_user: dict, file: UploadFile) -> dict:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_PROFILE_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and WEBP profile images are supported.",
        )

    binary = await file.read()
    if not binary:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded profile image is empty.")
    if len(binary) > MAX_PROFILE_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Profile image exceeds 2 MB limit.",
        )

    data_url = f"data:{content_type};base64,{base64.b64encode(binary).decode('ascii')}"
    await get_users_collection().update_one(
        {"_id": current_user["_id"]},
        {"$set": {"profile_image_data_url": data_url, "updated_at": _now_utc()}},
    )
    return {"profileImageUrl": data_url}


async def remove_profile_picture(current_user: dict) -> dict:
    await get_users_collection().update_one(
        {"_id": current_user["_id"]},
        {"$unset": {"profile_image_data_url": ""}, "$set": {"updated_at": _now_utc()}},
    )
    return {"profileImageUrl": None}

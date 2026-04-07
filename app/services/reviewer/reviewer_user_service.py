from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.core.database import get_users_collection
from app.core.security import get_password_hash
from app.schemas.reviewer.reviewer_user import (
    CreateReviewerRequest,
    CreateReviewerResponse,
    ReviewerLifecycleStatus,
)


def _generate_temporary_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _lifecycle_allows_login(status_value: ReviewerLifecycleStatus) -> bool:
    return status_value != ReviewerLifecycleStatus.EXPIRED


async def create_reviewer_user(payload: CreateReviewerRequest, current_user: dict) -> CreateReviewerResponse:
    users_col = get_users_collection()
    email_lower = payload.email.lower()
    if await users_col.find_one({"email": email_lower}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    username = payload.username.strip().lower()
    if await users_col.find_one({"username": username}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken.",
        )

    temporary_password = _generate_temporary_password()
    now = datetime.now(timezone.utc)
    lifecycle_status = payload.lifecycle_status
    user_doc = {
        "email": email_lower,
        "username": username,
        "hashed_password": get_password_hash(temporary_password),
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "full_name": f"{payload.first_name} {payload.last_name}".strip(),
        "job_title": payload.job_title,
        "designation": payload.designation,
        "department": payload.department,
        "language": payload.language,
        "time_zone": payload.time_zone,
        "account_status": lifecycle_status.value,
        "role": "reviewer",
        "provider": "credentials",
        "requires_password_change": True,
        "is_first_login": True,
        "mfa_enabled": False,
        "email_verified": False,
        "phone_verified": False,
        "is_active": _lifecycle_allows_login(lifecycle_status),
        "created_by_user_id": str(current_user.get("id") or current_user.get("_id")),
        "created_at": now,
        "updated_at": now,
    }
    if current_user.get("enterprise_profile_id"):
        user_doc["enterprise_profile_id"] = current_user["enterprise_profile_id"]

    result = await users_col.insert_one(user_doc)
    return CreateReviewerResponse(
        id=str(result.inserted_id),
        email=payload.email,
        firstName=payload.first_name,
        lastName=payload.last_name,
        jobTitle=payload.job_title,
        designation=payload.designation,
        department=payload.department,
        username=username,
        language=payload.language,
        timeZone=payload.time_zone,
        status=lifecycle_status,
        role="reviewer",
        requiresPasswordChange=True,
        isFirstLogin=True,
        temporaryPassword=temporary_password,
    )


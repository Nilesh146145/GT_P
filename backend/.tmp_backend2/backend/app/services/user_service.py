"""
User management — admin-provisioned reviewers and related persistence.
"""

import secrets
import string
from datetime import datetime

from fastapi import HTTPException, status

from app.core.database import get_users_collection
from app.core.security import get_password_hash
from app.schemas.users import (
    CreateReviewerRequest,
    CreateReviewerResponse,
    ReviewerLifecycleStatus,
)


def _generate_temporary_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _lifecycle_allows_login(s: ReviewerLifecycleStatus) -> bool:
    """EXPIRED accounts cannot authenticate."""
    return s != ReviewerLifecycleStatus.EXPIRED


async def create_reviewer_by_admin(payload: CreateReviewerRequest) -> CreateReviewerResponse:
    """
    Create a reviewer user with a random temporary password and full FSD profile fields.

    Caller must enforce admin-only access (router dependency).
    """
    col = get_users_collection()
    email_lower = payload.email.lower()
    if await col.find_one({"email": email_lower}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    username_key = payload.username.strip().lower()
    if await col.find_one({"username": username_key}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken.",
        )

    temp_password = _generate_temporary_password()
    now = datetime.utcnow()
    full_name = f"{payload.first_name} {payload.last_name}"
    ls = payload.lifecycle_status

    user_doc = {
        "email": email_lower,
        "username": username_key,
        "hashed_password": get_password_hash(temp_password),
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "full_name": full_name,
        "job_title": payload.job_title,
        "designation": payload.designation,
        "department": payload.department,
        "language": payload.language,
        "time_zone": payload.time_zone,
        "account_status": ls.value,
        "role": "reviewer",
        "provider": "credentials",
        "requires_password_change": True,
        "is_first_login": True,
        "is_mfa_enabled": False,
        "mfa_enabled": False,
        "mfa_secret": None,
        "mfa_temp_secret": None,
        "email_verified": False,
        "phone_verified": False,
        "is_active": _lifecycle_allows_login(ls),
        "failed_password_attempts": 0,
        "failed_totp_attempts": 0,
        "created_at": now,
        "updated_at": now,
    }

    result = await col.insert_one(user_doc)
    user_id = str(result.inserted_id)

    return CreateReviewerResponse(
        id=user_id,
        email=payload.email,
        firstName=payload.first_name,
        lastName=payload.last_name,
        jobTitle=payload.job_title,
        designation=payload.designation,
        department=payload.department,
        username=username_key,
        language=payload.language,
        timeZone=payload.time_zone,
        lifecycle_status=ls,
        role="reviewer",
        requiresPasswordChange=True,
        isFirstLogin=True,
        temporary_password=temp_password,
    )

"""
Contributor registration — creates a ``contributor`` user (no enterprise document).
"""

from datetime import datetime

from fastapi import HTTPException

from app.core.database import get_users_collection
from app.core.security import get_password_hash
from app.schemas.auth import AuthUser
from app.schemas.contributor_auth import ContributorRegisterRequest, ContributorRegisterResponse


async def register_contributor(payload: ContributorRegisterRequest) -> ContributorRegisterResponse:
    col = get_users_collection()
    if await col.find_one({"email": payload.email.lower()}):
        raise HTTPException(status_code=409, detail="Email already registered.")

    now = datetime.utcnow()
    full_name = f"{payload.first_name} {payload.last_name}"
    user_doc = {
        "email": payload.email.lower(),
        "hashed_password": get_password_hash(payload.password),
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "full_name": full_name,
        "role": "contributor",
        "provider": "credentials",
        "requires_password_change": False,
        "is_first_login": False,
        "is_mfa_enabled": False,
        "mfa_enabled": False,
        "mfa_secret": None,
        "mfa_temp_secret": None,
        "email_verified": False,
        "phone_verified": False,
        "is_active": True,
        "failed_password_attempts": 0,
        "failed_totp_attempts": 0,
        "created_at": now,
        "updated_at": now,
    }
    result = await col.insert_one(user_doc)
    user_id = str(result.inserted_id)

    auth_user = AuthUser(
        id=user_id,
        email=payload.email,
        firstName=payload.first_name,
        lastName=payload.last_name,
        role="contributor",
        provider="credentials",
        phoneVerified=False,
        emailVerified=False,
    )
    return ContributorRegisterResponse(user=auth_user)

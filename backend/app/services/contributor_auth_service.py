"""
Contributor registration — full profile stored under contributor_profile on the user document.
"""
from __future__ import annotations


import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.core.database import get_users_collection
from app.core.security import get_password_hash
from app.schemas.auth import AuthUser
from app.schemas.contributor_auth import ContributorRegisterRequest, ContributorRegisterResponse

logger = logging.getLogger(__name__)


def _build_contributor_profile(payload: ContributorRegisterRequest, now: datetime) -> dict:
    return {
        "contributor_type": payload.contributor_type,
        "country_of_residence": payload.country_of_residence.strip(),
        "date_of_birth": payload.date_of_birth.isoformat(),
        "time_zone": payload.time_zone.strip(),
        "weekly_availability_hours": payload.weekly_availability_hours,
        "department_category": payload.department_category.strip(),
        "department_other": payload.department_other.strip() if payload.department_other else None,
        "degree_qualification": payload.degree_qualification.strip() if payload.degree_qualification else None,
        "primary_skills": payload.primary_skills,
        "secondary_skills": payload.secondary_skills or [],
        "other_skills": payload.other_skills or [],
        "linkedin_url": payload.linkedin_url.strip() if payload.linkedin_url else None,
        "mentor_guide_acknowledged": payload.mentor_guide_acknowledged,
        "nda_signatory_legal_name": payload.nda_signatory_legal_name.strip(),
        "verification_email": payload.effective_verification_email(),
        "resume_file_key": payload.resume_file_key.strip() if payload.resume_file_key else None,
        "accept_terms_of_use": payload.accept_terms_of_use,
        "accept_code_of_conduct": payload.accept_code_of_conduct,
        "accept_privacy_policy": payload.accept_privacy_policy,
        "accept_harassment_policy": payload.accept_harassment_policy,
        "acknowledgments_accepted": payload.acknowledgments_accepted,
        "notify_new_tasks_opt_in": payload.notify_new_tasks_opt_in,
        "profile_completed_at": now,
    }


async def register_contributor(payload: ContributorRegisterRequest) -> ContributorRegisterResponse:
    col = get_users_collection()
    email_lower = payload.email.lower()
    ver_email_lower = payload.effective_verification_email()

    if await col.find_one({"email": email_lower}):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")
    if ver_email_lower != email_lower and await col.find_one({"email": ver_email_lower}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Verification email is already registered to another account.",
        )

    now = datetime.now(timezone.utc)
    full_name = f"{payload.first_name.strip()} {payload.last_name.strip()}".strip()
    contributor_profile = _build_contributor_profile(payload, now)

    user_doc = {
        "email": email_lower,
        "hashed_password": get_password_hash(payload.password),
        "first_name": payload.first_name.strip(),
        "last_name": payload.last_name.strip(),
        "full_name": full_name or email_lower.split("@")[0],
        "phone": payload.phone.strip(),
        "verification_email": ver_email_lower,
        "role": "contributor",
        "provider": "credentials",
        "mfa_enabled": False,
        "requires_password_change": False,
        "is_first_login": False,
        "email_verified": False,
        "phone_verified": False,
        "sso_only": False,
        "contributor_profile": contributor_profile,
        "created_at": now,
        "updated_at": now,
    }
    result = await col.insert_one(user_doc)
    user_id = str(result.inserted_id)

    auth_user = AuthUser(
        id=user_id,
        email=payload.email,
        firstName=payload.first_name.strip(),
        lastName=payload.last_name.strip(),
        role="contributor",
        provider="credentials",
        phoneVerified=False,
        emailVerified=False,
    )
    return ContributorRegisterResponse(user=auth_user)

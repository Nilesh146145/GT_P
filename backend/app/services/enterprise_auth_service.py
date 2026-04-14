"""
Enterprise Auth Service
───────────────────────
Handles enterprise admin registration using the new EnterpriseRegisterRequest schema.

Collections:
  enterprises — org-level document
  users       — admin user linked to enterprise
"""
from __future__ import annotations



import logging
from datetime import datetime

from fastapi import HTTPException

from bson import ObjectId
from bson.errors import InvalidId

from app.core.database import get_db, get_enterprises_collection, get_users_collection
from app.core.security import get_password_hash
from app.schemas.auth import AuthUser
from app.schemas.enterprise_auth import (
    EnterpriseCompanyProfile,
    EnterpriseRegisterRequest,
    EnterpriseRegisterResponse,
)

logger = logging.getLogger(__name__)


async def get_enterprise_company_profile(enterprise_profile_id: str) -> EnterpriseCompanyProfile | None:
    """Load public company fields for GET /auth/me when user is enterprise."""
    try:
        oid = ObjectId(enterprise_profile_id)
    except InvalidId:
        return None
    doc = await get_enterprises_collection().find_one({"_id": oid})
    if not doc:
        return None
    return EnterpriseCompanyProfile(
        enterprise_profile_id=str(doc["_id"]),
        org_name=doc.get("org_name") or "",
        org_type=doc.get("org_type") or "",
        org_type_other=doc.get("org_type_other"),
        industry=doc.get("industry") or "",
        industry_other=doc.get("industry_other"),
        company_size=doc.get("company_size") or "",
        website=doc.get("website"),
        hq_country=doc.get("hq_country"),
        hq_city=doc.get("hq_city"),
        admin_title=doc.get("admin_title") or "",
        admin_dept=doc.get("admin_dept"),
        incorporation_country=doc.get("incorporation_country"),
    )


async def register_enterprise(payload: EnterpriseRegisterRequest) -> EnterpriseRegisterResponse:
    col = get_users_collection()
    if await col.find_one({"email": payload.email.lower()}):
        raise HTTPException(status_code=409, detail="Email already registered.")

    db = get_db()
    now = datetime.utcnow()

    # Enterprise profile document
    enterprise_doc = {
        "org_name": payload.org_name,
        "org_type": payload.org_type,
        "org_type_other": payload.org_type_other,
        "industry": payload.industry,
        "industry_other": payload.industry_other,
        "company_size": payload.company_size,
        "website": payload.website,
        "hq_country": payload.hq_country,
        "hq_city": payload.hq_city,
        "admin_title": payload.admin_title,
        "admin_dept": payload.admin_dept,
        "incorporation_country": payload.incorporation_country,
        "incorporation_file_key": payload.incorporation_file_key,
        "admin_email": payload.email.lower(),
        "accept_tos": payload.accept_tos,
        "accept_pp": payload.accept_pp,
        "accept_esa": payload.accept_esa,
        "accept_ahp": payload.accept_ahp,
        "marketing_opt_in": payload.marketing_opt_in,
        "created_at": now,
        "updated_at": now,
    }
    ent_result = await db["enterprises"].insert_one(enterprise_doc)
    enterprise_profile_id = str(ent_result.inserted_id)

    # Admin user document
    full_name = f"{payload.first_name} {payload.last_name}"
    user_doc = {
        "email": payload.email.lower(),
        "hashed_password": get_password_hash(payload.password),
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "full_name": full_name,
        "role": "enterprise",
        "provider": "credentials",
        "phone": payload.phone,
        "enterprise_profile_id": enterprise_profile_id,
        "mfa_enabled": False,
        "requires_password_change": False,
        "is_first_login": False,
        "email_verified": False,
        "phone_verified": False,
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
        role="enterprise",
        provider="credentials",
        phoneVerified=False,
        emailVerified=False,
    )

    return EnterpriseRegisterResponse(
        user=auth_user,
        enterprise_profile_id=enterprise_profile_id,
    )

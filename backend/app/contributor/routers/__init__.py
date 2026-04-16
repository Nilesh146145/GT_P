"""Contributor HTTP API — all routes except public credential share links require authentication."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.contributor.dependencies import get_contributor_id, require_contributor_user
from app.contributor.routers import (
    credentials,
    dashboard,
    earnings,
    learning,
    messages,
    payouts,
    preferences,
    profile,
    settings,
    submissions,
    support,
    tasks,
)


class ContributorSessionOut(BaseModel):
    """Sanity check: same Bearer access token as enterprise; role must be contributor."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="MongoDB user id (JWT sub)")
    email: str | None = None
    role: str
    mfa_enabled: bool = Field(alias="mfaEnabled")
    auth_endpoints: str = Field(
        default=(
            "POST /api/v1/auth/login | POST /api/v1/auth/register/contributor | "
            "POST /api/v1/auth/refresh | /api/v1/auth/mfa/* | /api/v1/auth/oauth/*"
        ),
    )


session_router = APIRouter(prefix="/api/contributor", tags=["Contributor"])


@session_router.get("/session", response_model=ContributorSessionOut, summary="Contributor session (auth check)")
async def contributor_session(current_user: dict = Depends(require_contributor_user)) -> ContributorSessionOut:
    return ContributorSessionOut(
        id=current_user["id"],
        email=current_user.get("email"),
        role=str(current_user.get("role") or ""),
        mfaEnabled=bool(current_user.get("mfa_enabled")),
    )


# Bearer JWT + contributor role + MFA policy (same stack as wizard/enterprise).
protected = APIRouter(dependencies=[Depends(get_contributor_id)])
protected.include_router(credentials.router)
protected.include_router(dashboard.router)
protected.include_router(profile.router)
protected.include_router(tasks.router)
protected.include_router(submissions.router)
protected.include_router(earnings.router)
protected.include_router(payouts.router)
protected.include_router(preferences.router)
protected.include_router(settings.router)
protected.include_router(messages.router)
protected.include_router(learning.router)
protected.include_router(support.router)

router = APIRouter()
router.include_router(session_router)
router.include_router(protected)
router.include_router(credentials.public_router)

__all__ = ["router"]

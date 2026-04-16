from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user

_ENTERPRISE_ROLE_ALIASES = frozenset(
    {
        "enterprise",
        "enterprise_user",
        "enterpriseuser",
        "org_admin",
        "organization_admin",
        "organisation_admin",
    }
)


def _normalize_role(raw: Any) -> str:
    if raw is None:
        return "enterprise"
    normalized = str(raw).strip().lower()
    if not normalized:
        return "enterprise"
    if normalized in _ENTERPRISE_ROLE_ALIASES:
        return "enterprise"
    return normalized


async def require_billing_user(current_user: dict = Depends(get_current_user)) -> dict:
    role = _normalize_role(current_user.get("role"))
    if role in {"contributor", "admin", "enterprise"}:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Contributor or admin role required.",
    )


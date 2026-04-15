from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

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
_SUPPORTED_ROLES = frozenset({"enterprise", "contributor", "reviewer"})


def normalize_role(raw: Any, *, default: str | None = None) -> str | None:
    if raw is None:
        return default
    normalized = str(raw).strip().lower()
    if not normalized:
        return default
    if normalized in _ENTERPRISE_ROLE_ALIASES:
        return "enterprise"
    return normalized


def require_supported_role(raw: Any, *, field_name: str = "role") -> str:
    normalized = normalize_role(raw)
    if normalized not in _SUPPORTED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_ROLE",
                "message": f"Unsupported {field_name}. Allowed roles: enterprise, contributor, reviewer.",
            },
        )
    return normalized


def role_conflict_registered_message(existing_role: str) -> str:
    article = "an" if existing_role[:1] in {"a", "e", "i", "o", "u"} else "a"
    return f"This email is already registered as {article} {existing_role} account."


def role_conflict_login_message(requested_role: str) -> str:
    return f"This email cannot be used for {requested_role} login."

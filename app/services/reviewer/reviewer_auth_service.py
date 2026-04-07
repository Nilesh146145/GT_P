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


def normalize_role(raw: Any) -> str:
    if raw is None:
        return "enterprise"
    normalized = str(raw).strip().lower()
    if not normalized:
        return "enterprise"
    if normalized in _ENTERPRISE_ROLE_ALIASES:
        return "enterprise"
    return normalized


def is_reviewer_role(raw: Any) -> bool:
    return normalize_role(raw) == "reviewer"


def is_reviewer_admin(raw: Any) -> bool:
    return normalize_role(raw) in {"enterprise", "admin"}


def reviewer_requires_password_change(user: dict) -> bool:
    return is_reviewer_role(user.get("role")) and bool(user.get("requires_password_change", False))


def reviewer_mfa_completed(user: dict) -> bool:
    return bool(user.get("mfa_enabled", False))


def mfa_enrollment_required(user: dict) -> bool:
    return normalize_role(user.get("role")) in {"enterprise", "reviewer"} and not reviewer_mfa_completed(user)


def auth_user_flags(user: dict) -> dict[str, bool]:
    return {
        "requiresPasswordChange": reviewer_requires_password_change(user),
        "isFirstLogin": bool(user.get("is_first_login", False)),
        "mfaEnabled": reviewer_mfa_completed(user),
    }


def current_user_flags(user: dict) -> dict[str, bool]:
    return {
        **auth_user_flags(user),
        "mfaEnrollmentRequired": mfa_enrollment_required(user),
    }


def ensure_reviewer_admin_access(current_user: dict) -> None:
    if is_reviewer_admin(current_user.get("role")):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions for reviewer administration.",
    )


def ensure_reviewer_access(current_user: dict) -> None:
    if not is_reviewer_role(current_user.get("role")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer role required.",
        )
    if not reviewer_mfa_completed(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer MFA is required.",
        )
    if reviewer_requires_password_change(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Change your temporary password before using reviewer APIs.",
        )


def ensure_assignment_access(current_user: dict, reviewer_user_id: str) -> None:
    if is_reviewer_admin(current_user.get("role")):
        return
    if is_reviewer_role(current_user.get("role")) and str(current_user.get("id")) == str(reviewer_user_id):
        ensure_reviewer_access(current_user)
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admins may manage any reviewer queue. Reviewers may manage only their own queue.",
    )


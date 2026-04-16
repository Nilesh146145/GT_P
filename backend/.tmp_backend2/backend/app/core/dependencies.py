"""
FastAPI dependencies — RBAC and reviewer onboarding gates.

Uses ``get_current_user`` from security; does not duplicate JWT validation.
"""

from collections.abc import Callable
from typing import Any, Optional

from fastapi import Depends, HTTPException, status

from app.core.platform_admin import is_platform_admin
from app.core.security import get_current_user

# Legacy / alternate labels stored in MongoDB for org admins → canonical ``enterprise``
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


def normalize_system_role(raw: Any) -> str:
    """
    Canonical portal RBAC string from a user document's ``role`` field.

    Missing, empty, or whitespace-only values become ``enterprise`` (backward compatible).
    """

    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return "enterprise"
    s = str(raw).strip().lower()
    if not s:
        return "enterprise"
    if s in _ENTERPRISE_ROLE_ALIASES:
        return "enterprise"
    return s


def require_role(*allowed_roles: str) -> Callable[..., Any]:
    """
    Factory: dependency that ensures ``current_user["role"]`` is one of ``allowed_roles``.

    Existing users without a ``role`` field are treated as ``enterprise`` for backward
    compatibility.
    """

    allowed = frozenset(normalize_system_role(r) for r in allowed_roles)

    async def _checker(current_user: dict = Depends(get_current_user)) -> dict:
        role = normalize_system_role(current_user.get("role"))
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this resource.",
            )
        return current_user

    return _checker


async def check_reviewer_password_changed(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Reviewers still on the admin-issued temporary password cannot pass (403).

    Non-reviewers are unchanged. Use as the first link before ``require_active_reviewer``.
    """
    if _reviewer_must_change_password(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Change your temporary password before using reviewer tools.",
        )
    return current_user


async def check_reviewer_mfa_enabled(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Reviewers without completed TOTP enrollment cannot pass (403).

    Non-reviewers are unchanged.
    """
    role = normalize_system_role(current_user.get("role"))
    if role == "reviewer" and not _reviewer_mfa_satisfied(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA must be enabled for reviewer accounts.",
        )
    return current_user


# Backwards-compatible names for composition on reviewer-only routes.
check_first_login = check_reviewer_password_changed
check_mfa_enabled = check_reviewer_mfa_enabled


async def require_admin_or_platform_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Strict platform scope: DB role ``admin`` **or** ``PLATFORM_ADMIN_EMAILS`` only.

    For reviewer provisioning from **enterprise org admins**, use
    ``require_enterprise_org_admin_or_platform`` instead.
    """
    role = normalize_system_role(current_user.get("role"))
    if role == "admin" or is_platform_admin(current_user):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Insufficient permissions for this resource. "
            f"Requires platform admin role or allowlisted email; your role is '{role}'."
        ),
    )


async def require_enterprise_org_admin_or_platform(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    ``POST /users`` and reviewer-assignment routes under ``/users``.

    Allows **enterprise** org-admin accounts (role ``enterprise``), **platform**
    ``admin``, or emails in ``PLATFORM_ADMIN_EMAILS``.
    """
    role = normalize_system_role(current_user.get("role"))
    if role in ("admin", "enterprise") or is_platform_admin(current_user):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Insufficient permissions for this resource. "
            "Create reviewer users and assign reviewer tasks using an enterprise admin account "
            "(register via /auth/register/enterprise), a platform admin, or an email in "
            f"PLATFORM_ADMIN_EMAILS. Your account role is '{role}'."
        ),
    )


def ensure_can_manage_reviewer_assignments(current_user: dict, reviewer_user_id: str) -> None:
    """
    Who may list or create rows under ``/users/reviewers/{reviewer_user_id}/assignments``:

    - Enterprise org admin, platform ``admin``, or ``PLATFORM_ADMIN_EMAILS`` (any reviewer id).
    - Active reviewer **only when** ``reviewer_user_id`` equals their own ``current_user[\"id\"]``
      (password no longer temporary, MFA satisfied — same rules as ``/reviewer/*``).
    """
    role = normalize_system_role(current_user.get("role"))
    if role in ("admin", "enterprise") or is_platform_admin(current_user):
        return
    if role == "reviewer" and str(current_user.get("id")) == str(reviewer_user_id):
        reason = _reviewer_access_block_reason(current_user)
        if reason:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Insufficient permissions for this resource. "
            "Admins assign tasks to any reviewer; reviewers may only manage their own queue "
            "(use your user id in the path — see GET /auth/me). "
            f"Your account role is '{role}'."
        ),
    )


def _reviewer_mfa_satisfied(user: dict) -> bool:
    """Reviewers must keep TOTP MFA enabled (secret present + flags on)."""
    if not user.get("mfa_secret"):
        return False
    return bool(user.get("is_mfa_enabled") or user.get("mfa_enabled"))


def _reviewer_must_change_password(user: dict) -> bool:
    """
    True if this reviewer must still replace the admin-issued temporary password.

    Missing field is treated as false so legacy user documents stay usable.
    """
    role = normalize_system_role(user.get("role"))
    if role != "reviewer":
        return False
    return bool(user.get("requires_password_change", False))


def _reviewer_access_block_reason(user: dict) -> Optional[str]:
    """
    If this user is a reviewer and must not use reviewer APIs yet, return a short reason.

    Otherwise return ``None``.
    """
    role = normalize_system_role(user.get("role"))
    if role != "reviewer":
        return None
    if _reviewer_must_change_password(user):
        return "Change your temporary password before using reviewer tools."
    if not _reviewer_mfa_satisfied(user):
        return "MFA must be enabled for reviewer accounts."
    return None


async def require_reviewer_setup_complete(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Blocks reviewers until ``requires_password_change`` is cleared and MFA is enabled.

    Apply only to reviewer app routes (e.g. ``/reviewer/*``), not to setup endpoints
    (``/auth/password/change``, ``/auth/mfa/*``).
    """
    reason = _reviewer_access_block_reason(current_user)
    if reason:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason,
        )
    return current_user


async def require_enterprise_org_member(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Enterprise portal user with an organisation profile (``enterprise_profile_id``).

    Used for billing and other org-scoped modules (FSD §10).
    """
    role = normalize_system_role(current_user.get("role"))
    if role != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This resource is available to enterprise accounts only.",
        )
    eid = current_user.get("enterprise_profile_id")
    if not eid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No enterprise profile linked to this account.",
        )
    return current_user


async def require_active_reviewer(
    current_user: dict = Depends(check_reviewer_password_changed),
) -> dict:
    """
    Reviewer role + temp password replaced + MFA enabled.

    Chains ``check_reviewer_password_changed`` (one ``get_current_user``) then enforces
    role and MFA for ``role == reviewer``.
    """
    role = normalize_system_role(current_user.get("role"))
    if role != "reviewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this resource.",
        )
    if not _reviewer_mfa_satisfied(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA must be enabled for reviewer accounts.",
        )
    return current_user

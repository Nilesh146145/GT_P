"""
Platform-level admin helpers (env-based).

``PLATFORM_ADMIN_EMAILS`` is a comma-separated allowlist from **pydantic-settings**
(``app.core.config`` / ``.env``). Using ``os.getenv`` alone would miss ``.env`` when the
process environment is not pre-loaded.
"""

from typing import Any, Mapping

from app.core.config import settings


def _platform_admin_email_set() -> frozenset:
    raw = (settings.PLATFORM_ADMIN_EMAILS or "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def is_platform_admin(user: Mapping[str, Any]) -> bool:
    """True if ``user['email']`` is listed in ``PLATFORM_ADMIN_EMAILS`` (case-insensitive)."""
    email = (user.get("email") or "").strip().lower()
    return bool(email and email in _platform_admin_email_set())

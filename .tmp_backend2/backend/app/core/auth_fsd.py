"""
FSD GWIP Enterprise Portal §3 — authentication copy and rule IDs (API responses).

Reference: Functional Specification — Authentication, Session Management & MFA.
"""

from typing import Any, Dict, Optional

# ── AUTH-001 … AUTH-008 (§3.2.2) ─────────────────────────────────────────────

AUTH_001_NO_ACCOUNT = "No account found with this email address."
AUTH_002_WRONG_PASSWORD = "Incorrect password."
AUTH_003_LOCKED = (
    "Account locked for 15 minutes. An unlock link has been sent to your registered email."
)
AUTH_004_TOTP_INVALID = "Invalid verification code. Please try again."
AUTH_005_TOTP_REPLAY = (
    "This code has already been used. Please wait for the next 30-second code."
)
AUTH_007_PORTAL = "Your account does not have access to the Enterprise Portal."
AUTH_008_DEACTIVATED = "Your account has been deactivated. Please contact GlimmoraTeam support."

# MFA step-2 prompt (§3.3.4)
MFA_STEP2_MESSAGE = "Enter the 6-digit code from your authenticator app."

# Roles allowed to use Enterprise Portal APIs (§3.1 / §2)
PORTAL_ROLES = frozenset({"enterprise", "reviewer", "admin", "contributor"})


def err_detail(code: str, message: str, **extra: Any) -> Dict[str, Any]:
    d: Dict[str, Any] = {"code": code, "message": message}
    d.update(extra)
    return d


def wrong_password_detail(attempts_remaining: Optional[int]) -> Dict[str, Any]:
    """AUTH-002 with optional remaining attempts before lockout."""
    if attempts_remaining is not None and attempts_remaining > 0:
        msg = f"Incorrect password. [{attempts_remaining}] attempts remaining before lockout."
    else:
        msg = AUTH_002_WRONG_PASSWORD
    return err_detail("AUTH-002", msg, attempts_remaining=attempts_remaining)

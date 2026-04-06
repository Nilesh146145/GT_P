"""
Password Service
────────────────
Handles password reset initiation.

  start_password_reset(email, role) — generates a reset token,
  stores it in the password_resets collection, and logs it (dry-run).
  In production, wire this to your email delivery service.
"""


import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from app.core.database import get_db, get_users_collection

logger = logging.getLogger(__name__)


async def start_password_reset(email: str, role: Optional[str] = None) -> None:
    """
    Generate a password reset token for the given email (+ optional role filter).
    Always returns without error — never reveals whether the email exists
    (prevents user enumeration).

    In production: replace the logger.info call with your email gateway.
    """
    col = get_users_collection()
    query: dict = {"email": email.lower()}
    if role:
        query["role"] = role

    user = await col.find_one(query)
    if not user:
        # Silent no-op — don't expose whether the email is registered
        return

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    db = get_db()
    await db["password_resets"].insert_one({
        "user_id": str(user["_id"]),
        "email": email.lower(),
        "role": role,
        "token": token,
        "expires_at": expires_at,
        "used": False,
    })

    # TODO: replace with real email delivery in production
    logger.info("[DRY RUN] Password reset token for %s (role=%s): %s", email, role, token)

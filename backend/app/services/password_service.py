"""
Password Service
────────────────
Handles password reset initiation.

  start_password_reset(email, role) — generates a reset token,
  stores it in the password_resets collection, and logs it (dry-run).
  In production, wire this to your email delivery service.
"""
from __future__ import annotations



import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.database import get_db, get_sessions_collection, get_users_collection
from app.core.security import get_password_hash, verify_password

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


async def change_password(user_id: str, current_password: str, new_password: str) -> None:
    users_col = get_users_collection()
    try:
        object_id = ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user.") from exc

    user = await users_col.find_one({"_id": object_id})
    if not user or not user.get("hashed_password"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if not verify_password(current_password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )

    await users_col.update_one(
        {"_id": object_id},
        {
            "$set": {
                "hashed_password": get_password_hash(new_password),
                "requires_password_change": False,
                "is_first_login": False,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    await get_sessions_collection().update_many(
        {"user_id": user_id, "revoked_at": None},
        {"$set": {"revoked_at": datetime.now(timezone.utc)}},
    )

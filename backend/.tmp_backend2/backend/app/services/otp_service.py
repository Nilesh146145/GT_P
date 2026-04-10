"""
OTP Service
───────────
Handles generation, storage (MongoDB), and verification of 6-digit OTPs
for phone and email verification (Step 3 of contributor registration).

Current mode: DRY_RUN — OTPs are logged/returned in the response instead
of being sent via SMS/email. Flip settings.OTP_DRY_RUN = False and wire
in a real gateway (Twilio, SendGrid, etc.) for production.
"""

import random
import string
import logging
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

OTP_COLLECTION = "otp_codes"


def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _get_otp_collection():
    db = get_db()
    return db[OTP_COLLECTION]


async def send_otp(otp_type: str, target: str) -> str:
    """
    Generate a 6-digit OTP, persist it, and (in production) dispatch it.

    Returns the OTP string — only expose this to the caller in dry-run mode.
    """
    otp = _generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    col = _get_otp_collection()
    # Invalidate any existing unexpired OTP for this target + type
    await col.delete_many({"type": otp_type, "target": target})
    await col.insert_one({
        "type": otp_type,      # "phone" | "email"
        "target": target,
        "otp": otp,
        "verified": False,
        "expires_at": expires_at,
        "created_at": datetime.utcnow(),
    })

    if settings.OTP_DRY_RUN:
        logger.warning(
            "[DRY RUN] OTP for %s (%s): %s — NOT sent via gateway", otp_type, target, otp
        )
    else:
        # TODO: wire real gateway here
        if otp_type == "phone":
            _send_sms(target, otp)
        else:
            _send_email(target, otp)

    return otp


async def verify_otp(otp_type: str, target: str, otp: str) -> bool:
    """
    Return True if the OTP is valid and not expired; mark it consumed.
    """
    col = _get_otp_collection()
    record = await col.find_one({
        "type": otp_type,
        "target": target,
        "otp": otp,
        "verified": False,
        "expires_at": {"$gt": datetime.utcnow()},
    })
    if not record:
        return False
    await col.update_one({"_id": record["_id"]}, {"$set": {"verified": True}})
    return True


# ── Stub gateway functions (replace with real integrations) ──────────────────

def _send_sms(phone: str, otp: str) -> None:
    """Send OTP via SMS (Twilio / SNS / etc.)."""
    # import twilio.rest; client = Client(...); client.messages.create(...)
    raise NotImplementedError("Wire a real SMS gateway here")


def _send_email(email: str, otp: str) -> None:
    """Send OTP via email (SendGrid / SES / SMTP)."""
    # import sendgrid; ...
    raise NotImplementedError("Wire a real email gateway here")

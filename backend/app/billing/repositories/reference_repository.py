from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.core.database import get_database, get_users_collection

_USER_PAYER_TYPES = frozenset(
    {
        "user",
        "users",
        "contributor",
        "contributors",
        "reviewer",
        "reviewers",
        "admin",
        "enterprise",
    }
)

_COLLECTION_MAP = {
    "task": "tasks",
    "tasks": "tasks",
    "earning": "earnings",
    "earnings": "earnings",
    "payout": "payouts",
    "payouts": "payouts",
    "contributor_profile": "contributors",
    "reviewer_profile": "reviewers",
}


async def get_payer_summary(payer_type: str, payer_id: str) -> dict[str, Any] | None:
    normalized = str(payer_type or "").strip().lower()
    try:
        oid = ObjectId(payer_id)
    except Exception:
        oid = None

    if normalized in _USER_PAYER_TYPES and oid is not None:
        user = await get_users_collection().find_one({"_id": oid}, {"hashed_password": 0})
        if not user:
            return None
        return {
            "id": str(user["_id"]),
            "email": user.get("email"),
            "full_name": user.get("full_name"),
            "role": user.get("role"),
        }

    collection_name = _COLLECTION_MAP.get(normalized)
    if not collection_name or oid is None:
        return None

    document = await get_database()[collection_name].find_one({"_id": oid})
    if not document:
        return None

    label = (
        document.get("name")
        or document.get("title")
        or document.get("full_name")
        or document.get("email")
        or document.get("status")
    )
    return {
        "id": str(document["_id"]),
        "type": normalized,
        "label": label,
    }


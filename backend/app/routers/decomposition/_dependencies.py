from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.core.database import get_db
from app.core.security import get_current_user


async def require_enterprise_user(
    current_user: dict = Depends(get_current_user),
    _db=Depends(get_db),
) -> dict:
    if current_user.get("role") != "enterprise":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Enterprise access required")
    return current_user


def enterprise_profile_id(current_user: dict) -> str:
    """Decomposition routes require an enterprise profile scope (KO-003 / §8)."""
    eid = current_user.get("enterprise_profile_id")
    if not eid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Enterprise profile is required.")
    return str(eid)

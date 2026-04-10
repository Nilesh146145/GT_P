from fastapi import Depends

from app.core.security import get_current_user
from app.services.reviewer import reviewer_auth_service


async def require_reviewer_user(current_user: dict = Depends(get_current_user)) -> dict:
    reviewer_auth_service.ensure_reviewer_access(current_user)
    return current_user


async def require_reviewer_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    reviewer_auth_service.ensure_reviewer_admin_access(current_user)
    return current_user


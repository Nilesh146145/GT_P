from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers.decomposition._dependencies import enterprise_profile_id, require_enterprise_user
from app.schemas.decomposition.checklist import ChecklistUpdate
from app.services.decomposition import checklist_service

router = APIRouter()


@router.get("/{plan_id}/checklist")
async def get_checklist(
    plan_id: str,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await checklist_service.get_checklist(eid, plan_id)


@router.post("/{plan_id}/checklist")
async def update_checklist(
    plan_id: str,
    data: ChecklistUpdate,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await checklist_service.update_checklist(eid, plan_id, data)


@router.get("/{plan_id}/checklist/validate")
async def validate_checklist(
    plan_id: str,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await checklist_service.validate_checklist(eid, plan_id)


@router.get("/{plan_id}/checklist/date-validation")
async def validate_dates(
    plan_id: str,
    current_user: dict = Depends(require_enterprise_user),
):
    eid = enterprise_profile_id(current_user)
    return await checklist_service.validate_dates(eid, plan_id)

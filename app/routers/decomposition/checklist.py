from fastapi import APIRouter

from app.schemas.decomposition.checklist import ChecklistUpdate
from app.services.decomposition import checklist_service

router = APIRouter()


@router.get("/{plan_id}/checklist")
def get_checklist(plan_id: int):
    return checklist_service.get_checklist(plan_id)


@router.post("/{plan_id}/checklist")
def update_checklist(plan_id: int, data: ChecklistUpdate):
    return checklist_service.update_checklist(plan_id, data)


@router.get("/{plan_id}/checklist/validate")
def validate_checklist(plan_id: int):
    return checklist_service.validate_checklist(plan_id)


@router.get("/{plan_id}/checklist/date-validation")
def validate_dates(plan_id: int):
    return checklist_service.validate_dates(plan_id)

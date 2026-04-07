from fastapi import APIRouter

from app.services.decomposition import revision_service

router = APIRouter()


@router.get("/{plan_id}/revised")
def get_revised_plan(plan_id: int):
    return revision_service.get_revised_plan(plan_id)

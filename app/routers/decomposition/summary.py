from fastapi import APIRouter

from app.services.decomposition import summary_service

router = APIRouter()


@router.get("/{plan_id}/summary-panel")
def get_summary_panel(plan_id: int):
    return summary_service.get_summary_panel(plan_id)

from fastapi import APIRouter

from app.services.decomposition import revision_service

router = APIRouter()


@router.get("/{plan_id}/revisions/{revision_id}")
def get_revision_detail(plan_id: int, revision_id: int):
    return revision_service.get_revision_detail(plan_id, revision_id)

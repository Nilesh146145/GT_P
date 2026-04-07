from fastapi import APIRouter

from app.schemas.decomposition.revision import RevisionNotesRequest
from app.services.decomposition import revision_service

router = APIRouter()


@router.get("/{plan_id}/revision-modal")
def get_revision_modal(plan_id: int):
    return revision_service.get_revision_modal(plan_id)


@router.post("/{plan_id}/request-revision", operation_id="request_revision_plan")
def request_revision(plan_id: int, data: RevisionNotesRequest):
    return revision_service.request_revision(plan_id, data)

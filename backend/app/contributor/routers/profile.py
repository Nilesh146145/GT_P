from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.contributor.dependencies import get_contributor_id
from app.contributor.schemas.digital_twin import DigitalTwinHistoryResponse, DigitalTwinResponse, PeriodQuery
from app.contributor.schemas.evidence import EvidenceCreate, EvidenceListResponse, EvidenceResponse, EvidenceUpdate
from app.contributor.schemas.profile import ProfilePatchBody, ProfileResponse, SkillsPutBody
from app.contributor.services.profile_store import store

router = APIRouter(
    prefix="/api/contributor/profile",
    tags=["Contributor Profile"],
    dependencies=[Depends(get_contributor_id)],
)


def _validate_evidence_state(
    *,
    evidence_type: str,
    url: str | None,
    file_id: str | None,
) -> None:
    if evidence_type in ("link", "github"):
        if not url or not str(url).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="url is required for type link or github",
            )
    elif evidence_type == "file":
        if not file_id or not str(file_id).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="file_id is required for type file",
            )


@router.get("", response_model=ProfileResponse)
def get_profile(contributor_id: Annotated[str, Depends(get_contributor_id)]) -> ProfileResponse:
    return store.get_profile(contributor_id)


@router.patch("", response_model=ProfileResponse)
def patch_profile(
    body: ProfilePatchBody,
    contributor_id: Annotated[str, Depends(get_contributor_id)],
) -> ProfileResponse:
    data = body.model_dump(exclude_unset=True)
    return store.patch_profile(contributor_id, data)


@router.put("/skills", response_model=ProfileResponse)
def put_skills(
    body: SkillsPutBody,
    contributor_id: Annotated[str, Depends(get_contributor_id)],
) -> ProfileResponse:
    return store.put_skills(contributor_id, body.skills)


@router.get("/evidence", response_model=EvidenceListResponse)
def list_evidence(
    contributor_id: Annotated[str, Depends(get_contributor_id)],
    q: str | None = Query(None, description="Search title/description"),
    evidence_type: str | None = Query(None, alias="type", description="Filter by evidence type"),
    skill: str | None = Query(None, description="Filter by skill name"),
) -> EvidenceListResponse:
    items, total = store.list_evidence(contributor_id, q=q, type_filter=evidence_type, skill=skill)
    return EvidenceListResponse(items=items, total=total)


@router.post("/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
def create_evidence(
    body: EvidenceCreate,
    contributor_id: Annotated[str, Depends(get_contributor_id)],
) -> EvidenceResponse:
    return store.create_evidence(contributor_id, body.model_dump())


@router.patch("/evidence/{evidence_id}", response_model=EvidenceResponse)
def patch_evidence(
    evidence_id: str,
    body: EvidenceUpdate,
    contributor_id: Annotated[str, Depends(get_contributor_id)],
) -> EvidenceResponse:
    existing = store.get_evidence_row(contributor_id, evidence_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    patch = body.model_dump(exclude_unset=True)
    merged_type = patch.get("type", existing["type"])
    merged_url = patch["url"] if "url" in patch else existing.get("url")
    merged_file = patch["file_id"] if "file_id" in patch else existing.get("file_id")
    _validate_evidence_state(evidence_type=merged_type, url=merged_url, file_id=merged_file)
    updated = store.update_evidence(contributor_id, evidence_id, patch)
    assert updated is not None
    return updated


@router.delete("/evidence/{evidence_id}")
def delete_evidence(
    evidence_id: str,
    contributor_id: Annotated[str, Depends(get_contributor_id)],
) -> Response:
    if not store.delete_evidence(contributor_id, evidence_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/digital-twin", response_model=DigitalTwinResponse)
def get_digital_twin(contributor_id: Annotated[str, Depends(get_contributor_id)]) -> DigitalTwinResponse:
    return store.get_digital_twin(contributor_id)


@router.get("/digital-twin/history", response_model=DigitalTwinHistoryResponse)
def get_digital_twin_history(
    contributor_id: Annotated[str, Depends(get_contributor_id)],
    period: PeriodQuery = Query("3m", description="History window"),
) -> DigitalTwinHistoryResponse:
    return store.get_digital_twin_history(contributor_id, period)

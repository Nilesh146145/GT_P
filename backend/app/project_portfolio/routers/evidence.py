from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.project_portfolio.schemas.evidence_detail import EvidencePackDetail
from app.project_portfolio.services.evidence import get_evidence_pack_detail

router = APIRouter(tags=["evidence"])


@router.get("/evidence/{evidence_id}", response_model=EvidencePackDetail)
def view_evidence_pack(evidence_id: str) -> EvidencePackDetail:
    detail = get_evidence_pack_detail(evidence_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Evidence pack not found")
    return detail

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.project_portfolio.schemas.escalation import EscalationCreate, EscalationRecord
from app.project_portfolio.services.escalations import raise_escalation

router = APIRouter(tags=["escalations"])


@router.post("/escalations", response_model=EscalationRecord)
def create_escalation(body: EscalationCreate) -> EscalationRecord:
    record, err = raise_escalation(body)
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    if err == "rework_not_found":
        raise HTTPException(status_code=404, detail="Rework request not found")
    assert record is not None
    return record

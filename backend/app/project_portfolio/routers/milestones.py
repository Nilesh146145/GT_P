from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.project_portfolio.schemas.timeline import MilestoneDetail
from app.project_portfolio.services.timeline import get_milestone_detail

router = APIRouter(tags=["milestones"])


@router.get("/milestones/{milestone_id}", response_model=MilestoneDetail)
def read_milestone(milestone_id: str) -> MilestoneDetail:
    detail = get_milestone_detail(milestone_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return detail

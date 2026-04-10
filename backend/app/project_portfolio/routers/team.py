from fastapi import APIRouter, HTTPException

from app.project_portfolio.schemas.team import (
    SkillCoverageResponse,
    SkillReviewRequestBody,
    SkillReviewRequestResponse,
    TeamCompositionResponse,
)
from app.project_portfolio.services.team import (
    get_skill_coverage,
    get_team_composition,
    request_skill_coverage_review,
)

router = APIRouter(tags=["team"])


@router.get("/projects/{project_id}/team-composition", response_model=TeamCompositionResponse)
def get_team_composition_tab(project_id: str) -> TeamCompositionResponse:
    out = get_team_composition(project_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return out


@router.get("/projects/{project_id}/skill-coverage", response_model=SkillCoverageResponse)
def get_skill_coverage_tab(project_id: str) -> SkillCoverageResponse:
    out = get_skill_coverage(project_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return out


@router.post(
    "/projects/{project_id}/skill-review-request",
    response_model=SkillReviewRequestResponse,
)
def post_skill_review_request(
    project_id: str,
    body: SkillReviewRequestBody | None = None,
) -> SkillReviewRequestResponse:
    note = body.note if body else None
    out = request_skill_coverage_review(project_id, note=note)
    if out is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return out

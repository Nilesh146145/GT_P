from fastapi import APIRouter, HTTPException, Query, Response

from app.project_portfolio.schemas.project import (
    PortfolioProjectSort,
    PortfolioSummaryMetrics,
    ProjectCardSummary,
    ProjectHealth,
    ProjectListResponse,
    ProjectMilestone,
    ProjectStatus,
)
from app.project_portfolio.services.projects import (
    build_portfolio_export_csv,
    get_portfolio_summary_metrics,
    get_project_card_summary,
    list_projects_for_dashboard,
)

router = APIRouter(tags=["portfolio"])

_ALLOWED_HEALTH = ", ".join(item.value for item in ProjectHealth)
_ALLOWED_STATUS = ", ".join(item.value for item in ProjectStatus)
_ALLOWED_MILESTONE = ", ".join(item.value for item in ProjectMilestone)


def _parse_health_query(raw: str | None) -> list[ProjectHealth] | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    values: list[ProjectHealth] = []
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            values.append(ProjectHealth(token))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid health value {token!r}. "
                    f"Use one or more of: {_ALLOWED_HEALTH} (comma-separated)."
                ),
            ) from exc
    return values or None


def _parse_status_query(raw: str | None) -> list[ProjectStatus] | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    values: list[ProjectStatus] = []
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            values.append(ProjectStatus(token))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid status value {token!r}. "
                    f"Use one or more of: {_ALLOWED_STATUS} (comma-separated)."
                ),
            ) from exc
    return values or None


def _parse_milestone_query(raw: str | None) -> list[ProjectMilestone] | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    values: list[ProjectMilestone] = []
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            values.append(ProjectMilestone(token))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid milestone value {token!r}. "
                    f"Use one or more of: {_ALLOWED_MILESTONE} (comma-separated)."
                ),
            ) from exc
    return values or None


@router.get("/portfolio/projects", response_model=ProjectListResponse)
def get_projects_for_dashboard(
    health: str | None = Query(
        default=None,
        description="Filter by health; comma-separated for multiple, e.g. BEHIND,AT_RISK",
    ),
    status: str | None = Query(
        default=None,
        description="Filter by status; comma-separated for multiple, e.g. REWORK or active,REWORK",
    ),
    milestone: str | None = Query(
        default=None,
        description="Filter by milestone; comma-separated for multiple, e.g. M2_OVERDUE",
    ),
    sort_by: PortfolioProjectSort | None = Query(
        default=None,
        description="Sort result set; use `completion` for completion % descending.",
    ),
) -> ProjectListResponse:
    health_any = _parse_health_query(health)
    status_any = _parse_status_query(status)
    milestone_any = _parse_milestone_query(milestone)
    return ProjectListResponse(
        projects=list_projects_for_dashboard(
            health_any=health_any,
            status_any=status_any,
            milestone_any=milestone_any,
            sort_by=sort_by,
        ),
    )


@router.get("/portfolio/export")
def export_portfolio() -> Response:
    payload = build_portfolio_export_csv()
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="portfolio_export.csv"'},
    )


@router.get("/portfolio/project-summary/{project_id}", response_model=ProjectCardSummary)
def get_project_summary(project_id: str) -> ProjectCardSummary:
    summary = get_project_card_summary(project_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return summary


@router.get("/portfolio/summary-metrics", response_model=PortfolioSummaryMetrics)
def get_summary_metrics() -> PortfolioSummaryMetrics:
    return get_portfolio_summary_metrics()

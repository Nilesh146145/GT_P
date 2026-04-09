import csv
import io
from datetime import UTC, datetime

from app.project_portfolio.schemas.project import (
    ActivityItem,
    PortfolioProjectSort,
    PortfolioSummaryMetrics,
    ProjectCardSummary,
    ProjectDashboardItem,
    ProjectDetail,
    ProjectHealth,
    ProjectMilestone,
    ProjectOverview,
    ProjectStatus,
)

_DEMO_PROJECTS: list[ProjectDashboardItem] = [
    ProjectDashboardItem(
        id="proj_001",
        name="Brand refresh",
        summary="Visual identity and marketing site",
        status=ProjectStatus.ACTIVE,
        health=ProjectHealth.BEHIND,
        milestone=ProjectMilestone.M2_OVERDUE,
        completion_pct=45.0,
        updated_at=datetime(2026, 3, 15, 10, 0, tzinfo=UTC),
    ),
    ProjectDashboardItem(
        id="proj_002",
        name="Analytics pipeline",
        summary="ETL and reporting dashboards",
        status=ProjectStatus.ACTIVE,
        health=ProjectHealth.AT_RISK,
        milestone=ProjectMilestone.ON_TRACK,
        completion_pct=78.5,
        updated_at=datetime(2026, 4, 1, 14, 30, tzinfo=UTC),
    ),
    ProjectDashboardItem(
        id="proj_003",
        name="Mobile beta",
        summary=None,
        status=ProjectStatus.REWORK,
        health=ProjectHealth.AT_RISK,
        milestone=ProjectMilestone.M2_OVERDUE,
        completion_pct=20.0,
        updated_at=datetime(2026, 4, 5, 9, 15, tzinfo=UTC),
    ),
    ProjectDashboardItem(
        id="proj_004",
        name="Q1 launch recap",
        summary="Post-launch report and retro",
        status=ProjectStatus.COMPLETED,
        health=ProjectHealth.OK,
        milestone=ProjectMilestone.ON_TRACK,
        completion_pct=100.0,
        updated_at=datetime(2026, 4, 6, 16, 0, tzinfo=UTC),
    ),
]

_hold_by_project_id: dict[str, bool] = {}
_owner_by_project_id: dict[str, str] = {
    "proj_001": "Demo Owner",
    "proj_002": "Demo Owner",
    "proj_003": "Demo Owner",
    "proj_004": "Demo Owner",
}


def _get_project_row(project_id: str) -> ProjectDashboardItem | None:
    for project in _DEMO_PROJECTS:
        if project.id == project_id:
            return project
    return None


def project_exists(project_id: str) -> bool:
    return _get_project_row(project_id) is not None


def create_project_kickoff(
    *,
    project_id: str,
    name: str,
    summary: str | None,
    owner: str | None,
) -> tuple[ProjectDetail | None, str | None]:
    if _get_project_row(project_id) is not None:
        return None, "project_exists"
    now = datetime.now(tz=UTC)
    row = ProjectDashboardItem(
        id=project_id,
        name=name,
        summary=summary,
        status=ProjectStatus.ACTIVE,
        health=ProjectHealth.OK,
        milestone=ProjectMilestone.ON_TRACK,
        completion_pct=0.0,
        updated_at=now,
    )
    _DEMO_PROJECTS.append(row)
    _owner_by_project_id[project_id] = (owner or "Demo Owner").strip() or "Demo Owner"
    _hold_by_project_id[project_id] = False
    return get_project_detail(project_id), None


def update_project_status(
    *,
    project_id: str,
    to_status: ProjectStatus | str,
    actor_role: str,
) -> tuple[ProjectDetail | None, str | None]:
    row = _get_project_row(project_id)
    if row is None:
        return None, "project_not_found"
    from_status = row.status
    if isinstance(to_status, str):
        token = to_status.strip()
        matched = next(
            (
                s
                for s in ProjectStatus
                if token == s.value or token.upper() == s.value.upper() or token.upper() == s.name
            ),
            None,
        )
        if matched is None:
            return None, "invalid_transition"
        to_status = matched
    allowed: dict[ProjectStatus, set[ProjectStatus]] = {
        ProjectStatus.BACKLOG: {ProjectStatus.IN_PROGRESS},
        ProjectStatus.IN_PROGRESS: {ProjectStatus.IN_REVIEW},
        ProjectStatus.IN_REVIEW: {ProjectStatus.ACCEPTED, ProjectStatus.REWORK},
        ProjectStatus.REWORK: {ProjectStatus.IN_PROGRESS},
        ProjectStatus.ACCEPTED: {ProjectStatus.COMPLETED},
        ProjectStatus.ACTIVE: {ProjectStatus.IN_PROGRESS, ProjectStatus.ON_HOLD},
        ProjectStatus.ON_HOLD: {ProjectStatus.IN_PROGRESS, ProjectStatus.ACTIVE},
        ProjectStatus.DRAFT: {ProjectStatus.ACTIVE},
        ProjectStatus.COMPLETED: set(),
        ProjectStatus.ARCHIVED: set(),
    }
    if to_status == from_status:
        return get_project_detail(project_id), None
    if to_status not in allowed.get(from_status, set()):
        return None, "invalid_transition"
    manager_only = {ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED}
    role = actor_role.strip().lower()
    if to_status in manager_only and role not in {"manager", "admin"}:
        return None, "forbidden"

    row.status = to_status
    row.updated_at = datetime.now(tz=UTC)
    if to_status == ProjectStatus.ON_HOLD:
        _hold_by_project_id[project_id] = True
    elif from_status == ProjectStatus.ON_HOLD:
        _hold_by_project_id[project_id] = False
    return get_project_detail(project_id), None


def get_project_detail(project_id: str) -> ProjectDetail | None:
    row = _get_project_row(project_id)
    if row is None:
        return None
    on_hold = _hold_by_project_id.get(project_id, False)
    return ProjectDetail(**row.model_dump(), on_hold=on_hold)


def set_project_on_hold(project_id: str, *, on_hold: bool) -> ProjectDetail | None:
    if _get_project_row(project_id) is None:
        return None
    _hold_by_project_id[project_id] = on_hold
    return get_project_detail(project_id)


def get_project_overview(project_id: str) -> ProjectOverview | None:
    detail = get_project_detail(project_id)
    if detail is None:
        return None
    highlights: list[str] = [
        f"Completion {detail.completion_pct:g}%",
        f"Milestone: {detail.milestone.value}",
    ]
    if detail.summary:
        highlights.insert(0, detail.summary)
    return ProjectOverview(
        project_id=detail.id,
        name=detail.name,
        summary=detail.summary,
        status=detail.status,
        health=detail.health,
        milestone=detail.milestone,
        completion_pct=detail.completion_pct,
        on_hold=detail.on_hold,
        owner=_owner_by_project_id.get(project_id, "Demo Owner"),
        highlights=highlights[:8],
    )


def list_project_activities(project_id: str) -> list[ActivityItem] | None:
    row = _get_project_row(project_id)
    if row is None:
        return None
    return [
        ActivityItem(
            id=f"{project_id}_act_1",
            kind="milestone",
            title="Milestone check-in",
            detail=f'Tracking progress for "{row.name}".',
            actor="System",
            occurred_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
        ),
        ActivityItem(
            id=f"{project_id}_act_2",
            kind="status_change",
            title="Project status synced",
            detail=None,
            actor="Alex",
            occurred_at=datetime(2026, 4, 5, 14, 20, tzinfo=UTC),
        ),
        ActivityItem(
            id=f"{project_id}_act_3",
            kind="comment",
            title="Comment",
            detail="Weekly sync notes captured in the project log.",
            actor="Jamie",
            occurred_at=datetime(2026, 4, 4, 11, 45, tzinfo=UTC),
        ),
    ]


def list_projects_for_dashboard(
    *,
    health_any: list[ProjectHealth] | None = None,
    status_any: list[ProjectStatus] | None = None,
    milestone_any: list[ProjectMilestone] | None = None,
    sort_by: PortfolioProjectSort | None = None,
) -> list[ProjectDashboardItem]:
    projects = list(_DEMO_PROJECTS)
    if health_any:
        allowed_health = frozenset(health_any)
        projects = [p for p in projects if p.health in allowed_health]
    if status_any:
        allowed_status = frozenset(status_any)
        projects = [p for p in projects if p.status in allowed_status]
    if milestone_any:
        allowed_ms = frozenset(milestone_any)
        projects = [p for p in projects if p.milestone in allowed_ms]
    if sort_by == PortfolioProjectSort.COMPLETION:
        projects = sorted(projects, key=lambda p: p.completion_pct, reverse=True)
    return projects


def list_completed_projects() -> list[ProjectDashboardItem]:
    return list_projects_for_dashboard(
        health_any=None,
        status_any=[ProjectStatus.COMPLETED],
        milestone_any=None,
        sort_by=None,
    )


def get_project_card_summary(project_id: str) -> ProjectCardSummary | None:
    for project in _DEMO_PROJECTS:
        if project.id == project_id:
            return ProjectCardSummary(
                id=project.id,
                name=project.name,
                status=project.status,
            )
    return None


def get_portfolio_summary_metrics() -> PortfolioSummaryMetrics:
    projects = list_projects_for_dashboard(
        health_any=None,
        status_any=None,
        milestone_any=None,
        sort_by=None,
    )
    active = sum(1 for p in projects if p.status == ProjectStatus.ACTIVE)
    draft = sum(1 for p in projects if p.status == ProjectStatus.DRAFT)
    archived = sum(1 for p in projects if p.status == ProjectStatus.ARCHIVED)
    return PortfolioSummaryMetrics(
        total_projects=len(projects),
        active=active,
        draft=draft,
        archived=archived,
    )


def build_portfolio_export_csv() -> str:
    rows = list_projects_for_dashboard(
        health_any=None,
        status_any=None,
        milestone_any=None,
        sort_by=None,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "name",
            "summary",
            "status",
            "health",
            "milestone",
            "completion_pct",
            "updated_at",
        ],
    )
    for p in rows:
        writer.writerow(
            [
                p.id,
                p.name,
                p.summary or "",
                p.status.value,
                p.health.value,
                p.milestone.value,
                p.completion_pct,
                p.updated_at.isoformat(),
            ],
        )
    return buffer.getvalue()


def build_project_report_csv(project_id: str) -> str | None:
    detail = get_project_detail(project_id)
    if detail is None:
        return None
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "name",
            "summary",
            "status",
            "health",
            "milestone",
            "completion_pct",
            "updated_at",
            "on_hold",
        ],
    )
    writer.writerow(
        [
            detail.id,
            detail.name,
            detail.summary or "",
            detail.status.value,
            detail.health.value,
            detail.milestone.value,
            detail.completion_pct,
            detail.updated_at.isoformat(),
            detail.on_hold,
        ],
    )
    return buffer.getvalue()


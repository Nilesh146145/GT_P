from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ProjectHealth(str, Enum):
    OK = "OK"
    AT_RISK = "AT_RISK"
    BEHIND = "BEHIND"


class ProjectStatus(str, Enum):
    BACKLOG = "BACKLOG"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    ACCEPTED = "ACCEPTED"
    ON_HOLD = "ON_HOLD"
    ACTIVE = "active"
    DRAFT = "draft"
    ARCHIVED = "archived"
    REWORK = "REWORK"
    COMPLETED = "completed"


class ProjectMilestone(str, Enum):
    ON_TRACK = "ON_TRACK"
    M1_DUE = "M1_DUE"
    M2_OVERDUE = "M2_OVERDUE"


class PortfolioProjectSort(str, Enum):
    COMPLETION = "completion"


class ProjectDashboardItem(BaseModel):
    """Project row as shown on the portfolio dashboard."""

    id: str
    name: str
    summary: str | None = None
    status: ProjectStatus
    health: ProjectHealth = Field(description="portfolio health signal for filtering")
    milestone: ProjectMilestone
    completion_pct: float = Field(ge=0, le=100, description="0-100 for sorting by completion")
    updated_at: datetime


class ProjectDetail(ProjectDashboardItem):
    """Full project for view screen; includes workflow flags stored in memory."""

    on_hold: bool = False


class ProjectListResponse(BaseModel):
    projects: list[ProjectDashboardItem]


class ProjectCardSummary(BaseModel):
    """Minimal fields for a project card on the dashboard."""

    id: str
    name: str
    status: ProjectStatus


class PortfolioSummaryMetrics(BaseModel):
    """Aggregate counts for dashboard header metrics."""

    total_projects: int
    active: int
    draft: int
    archived: int


class ProjectOverview(BaseModel):
    """TAB-1 overview: summary for the project detail screen."""

    project_id: str
    name: str
    summary: str | None = None
    status: ProjectStatus
    health: ProjectHealth
    milestone: ProjectMilestone
    completion_pct: float
    on_hold: bool
    owner: str | None = Field(default=None, description="Accountable owner display name")
    highlights: list[str] = Field(default_factory=list)


class ActivityItem(BaseModel):
    """Single row in the activity feed."""

    id: str
    kind: str = Field(description="e.g. status_change, comment, milestone, escalation")
    title: str
    detail: str | None = None
    actor: str
    occurred_at: datetime


class ActivityFeedResponse(BaseModel):
    activities: list[ActivityItem]


class KickoffCreateRequest(BaseModel):
    project_id: str
    name: str
    summary: str | None = None
    owner: str | None = None


class ProjectStatusUpdateRequest(BaseModel):
    to_status: str = Field(description="Target status; accepts enum value case-insensitively.")
    actor_role: str = Field(
        default="contributor",
        description="Use contributor or manager/admin for guarded transitions.",
    )
    note: str | None = None


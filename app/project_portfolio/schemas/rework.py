from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReworkRequestStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class ReworkRequest(BaseModel):
    """TAB-4: single rework row."""

    id: str
    project_id: str
    task_id: str
    task: str = Field(description="Task title / label")
    milestone_id: str
    milestone: str = Field(description="Milestone display name")
    reason: str
    deadline: datetime
    round: int = Field(ge=1, description="Rework round number")
    status: ReworkRequestStatus


class ReworkRequestsResponse(BaseModel):
    project_id: str
    page: int
    limit: int
    total: int
    status_filter: ReworkRequestStatus | None = None
    milestone_filter: str | None = None
    round_filter: int | None = None
    task_query: str | None = None
    deadline_from: date | None = None
    deadline_to: date | None = None
    rework_requests: list[ReworkRequest]


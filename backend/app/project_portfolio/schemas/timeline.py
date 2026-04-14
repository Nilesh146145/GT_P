from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TimelineView(str, Enum):
    GANTT = "gantt"
    LIST = "list"


class TimelineTask(BaseModel):
    id: str
    title: str
    start_at: datetime
    end_at: datetime
    status: str = Field(description="e.g. todo, in_progress, done")
    depends_on_task_ids: list[str] = Field(default_factory=list)


class TimelineMilestone(BaseModel):
    """Milestone with nested tasks for TAB-2 timeline."""

    id: str
    name: str
    start_at: datetime
    end_at: datetime
    status: str
    tasks: list[TimelineTask]


class ProjectTimelineResponse(BaseModel):
    """TAB-2: milestone + task data for gantt or list view."""

    project_id: str
    view: TimelineView
    milestones: list[TimelineMilestone]


class MilestoneDetail(BaseModel):
    """Full milestone for side panel (click from gantt/list)."""

    id: str
    project_id: str
    name: str
    description: str | None = None
    start_at: datetime
    end_at: datetime
    status: str
    deliverables: list[str] = Field(default_factory=list)
    tasks: list[TimelineTask]

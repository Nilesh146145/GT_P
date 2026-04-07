from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.models.decomposition import PlanSummaryStats, PlanSummaryStrip


class SummaryPanelResponse(BaseModel):
    total_milestones: int
    total_tasks: int
    total_effort_days: int
    critical_path_days: int
    critical_tasks_count: int
    skills: list[str]
    sow_start: date
    sow_end: date
    plan_start: date
    plan_end: date
    date_warning: str | None = None

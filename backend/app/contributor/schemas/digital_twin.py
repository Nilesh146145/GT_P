from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PeriodQuery = Literal["3m", "6m", "1y"]


class TopSkill(BaseModel):
    name: str
    score: float | None = None


class MonthlyActivity(BaseModel):
    month: str
    tasks: int | None = None
    hours: float | None = None


class DigitalTwinResponse(BaseModel):
    updated_at: datetime | None = None
    tasks_completed: int | None = None
    total_submissions: int | None = None
    acceptance_rate: float | None = None
    on_time_delivery: float | None = None
    sla_compliance: float | None = None
    average_review_score: float | None = None
    total_hours_logged: float | None = None
    average_hours_per_task: float | None = None
    skill_growth_rate: float | None = None
    rework_rate: float | None = None
    streak_days: int | None = None
    longest_streak: int | None = None
    top_skills: list[TopSkill] = Field(default_factory=list)
    monthly_activity: list[MonthlyActivity] = Field(default_factory=list)
    ai_insights: list[str | dict[str, Any]] = Field(default_factory=list)


class DigitalTwinHistoryResponse(BaseModel):
    period: PeriodQuery
    snapshots: list[dict[str, Any]] = Field(default_factory=list)

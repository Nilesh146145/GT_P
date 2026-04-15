from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class AssessmentBreakdown(BaseModel):
    overall: float
    mcq: float
    work_sample: float
    adaptive: float
    last_assessed_at: datetime | None = None


class PlatformTrackRecord(BaseModel):
    tasks_completed: int
    acceptance_rate: float
    average_rework_rounds: float
    active_since: datetime | None = None


class DesignationInfo(BaseModel):
    designation: str
    seniority_level: str


class ProfileOverviewResponse(BaseModel):
    designation_badge: DesignationInfo
    assessment_summary: AssessmentBreakdown
    platform_track_record: PlatformTrackRecord
    profile_completeness: float
    request_reassessment_eligible: bool


class VerifiedSkill(BaseModel):
    name: str
    assessment_score: float | None = None
    last_verified_at: datetime | None = None


class DeclaredSkill(BaseModel):
    name: str


class SkillsDetailsResponse(BaseModel):
    verified_skills: list[VerifiedSkill] = Field(default_factory=list)
    declared_skills: list[DeclaredSkill] = Field(default_factory=list)
    tech_stack_tools: list[str] = Field(default_factory=list)
    domain_expertise: list[str] = Field(default_factory=list)


class AddDeclaredSkillBody(BaseModel):
    name: str


class SkillsDetailsPatchBody(BaseModel):
    tech_stack_tools: list[str] | None = None
    domain_expertise: list[str] | None = None


PreferredTaskSize = Literal["small", "medium", "large", "no_preference"]


class DateRangeEntry(BaseModel):
    id: str
    start_date: date
    end_date: date
    label: str | None = None


class AvailabilityResponse(BaseModel):
    last_updated_at: datetime
    last_updated_days_ago: int
    stale_level: Literal["ok", "amber", "red"]
    maximum_weekly_hours: float
    current_weekly_availability: float
    preferred_task_size: PreferredTaskSize
    max_concurrent_projects: int
    blackout_dates: list[DateRangeEntry] = Field(default_factory=list)
    academic_calendar: list[DateRangeEntry] = Field(default_factory=list)


class AvailabilityPatchBody(BaseModel):
    maximum_weekly_hours: float | None = None
    current_weekly_availability: float | None = None
    preferred_task_size: PreferredTaskSize | None = None
    max_concurrent_projects: int | None = None


class DateRangeCreateBody(BaseModel):
    start_date: date
    end_date: date
    label: str | None = None

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    NEW = "NEW"
    PENDING_KICKOFF = "PENDING_KICKOFF"
    PLAN_REVIEW_REQUIRED = "PLAN_REVIEW_REQUIRED"
    REVISION_IN_PROGRESS = "REVISION_IN_PROGRESS"
    PLAN_CONFIRMED = "PLAN_CONFIRMED"
    PLAN_LOCKED = "PLAN_LOCKED"


class PlanPhase(BaseModel):
    phase_number: int
    phase_name: str
    duration_weeks: int
    deliverables: list[str]
    assigned_team: str


class PlanRisk(BaseModel):
    risk_id: str
    description: str
    severity: str
    mitigation: str


class BudgetBreakdown(BaseModel):
    total_estimated_cost: str
    currency: str
    breakdown: dict


class PlanSummaryStats(BaseModel):
    total_milestones: int
    total_tasks: int
    estimated_total_effort_days: int
    project_start: str
    project_end: str
    critical_path_task_count: int


class PlanResponse(BaseModel):
    plan_id: str
    project_name: str
    project_description: str
    sow_reference: str
    plan_version: int
    status: PlanStatus
    dashboard_message: str
    is_read_only: bool
    is_urgent: bool
    revision_count: int = 0
    max_revisions: int = 3
    revision_limit_reached: bool = False
    revision_estimated_minutes: Optional[str] = None
    revision_requested_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    locked_at: Optional[str] = None
    locked_by_contributor_id: Optional[str] = None
    summary: PlanSummaryStats
    objective: str
    scope: str
    total_duration_weeks: int
    phases: list[PlanPhase]
    risks: list[PlanRisk]
    budget: BudgetBreakdown
    success_metrics: list[str]
    assumptions: list[str]
    agi_confidence_score: float
    generated_by: str
    generated_at: str
    enterprise_deadline_to_confirm: str
    plan_exceeds_sow_by_days: Optional[int] = None


class ConfirmPlanRequest(BaseModel):
    confirmed_by: str


class RevisionRequest(BaseModel):
    requested_by: str
    revision_notes: str = Field(..., min_length=30, max_length=2000)


class CreateDecompositionPlanRequest(BaseModel):
    """Create a server-side plan (KO-003 PENDING_KICKOFF) before kick-off releases it to the enterprise."""

    sow_reference: str
    project_name: str
    sow_version: str = "1"
    sow_start: Optional[str] = None
    sow_end: Optional[str] = None


class LockPlanRequest(BaseModel):
    contributor_id: str
    assignment_offer_id: str


class PlanStatusResponse(BaseModel):
    plan_id: str
    project_name: str
    status: PlanStatus
    dashboard_message: str
    is_read_only: bool
    is_urgent: bool
    revision_estimated_minutes: Optional[str] = None
    sow_reference: Optional[str] = None
    sow_version: Optional[str] = None
    milestone_count: Optional[int] = None
    task_count: Optional[int] = None
    plan_exceeds_sow_by_days: Optional[int] = None


class EmptyStateLink(BaseModel):
    label: str
    url: str


class EmptyStateResponse(BaseModel):
    empty: bool = True
    reason: str
    message: str
    cta: Optional[EmptyStateLink] = None
    links: Optional[list[EmptyStateLink]] = None


class RevisionRound(str, Enum):
    ROUND_0 = "ROUND_0"
    ROUND_1 = "ROUND_1"
    ROUND_2 = "ROUND_2"
    ROUND_3 = "ROUND_3"


class PlanSummaryStrip(BaseModel):
    total_milestones: int
    total_tasks: int
    estimated_effort_days: int
    project_start: str
    project_end: str
    critical_path_tasks: int


class ReviewChecklistItem(BaseModel):
    item_id: str
    label: str
    is_checked: bool


class PlanReviewPageResponse(BaseModel):
    plan_id: str
    project_name: str
    sow_reference: str
    plan_version: str
    status: PlanStatus
    revision_round: RevisionRound
    revision_label: str
    max_revisions_reached: bool
    revision_warning: Optional[str] = None
    can_request_revision: bool
    can_confirm_plan: bool
    revision_in_progress: bool
    summary: PlanSummaryStrip
    checklist: list[ReviewChecklistItem]
    checklist_complete: bool


class ChecklistUpdateRequest(BaseModel):
    item_id: str
    is_checked: bool
    updated_by: str


class ChecklistUpdateResponse(BaseModel):
    plan_id: str
    item_id: str
    is_checked: bool
    checklist_complete: bool
    can_confirm_plan: bool

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    available = "available"
    in_progress = "in_progress"
    submitted = "submitted"
    completed = "completed"
    rework = "rework"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class TimeFilter(str, Enum):
    week = "week"
    month = "month"


class TaskSortBy(str, Enum):
    task = "task"
    project = "project"
    status = "status"
    priority = "priority"
    match = "match"
    due_date = "due_date"
    pricing = "pricing"
    # Task Discovery (§7.1) — passive feed sorts
    offer_expiry = "offer_expiry"
    shortest_effort = "shortest_effort"
    recent = "recent"


class SortDir(str, Enum):
    asc = "asc"
    desc = "desc"


class DeclineReason(str, Enum):
    """Legacy codes plus Task Discovery §7.5 options."""

    schedule_conflict = "schedule_conflict"
    skills_mismatch = "skills_mismatch"
    scope_too_large = "scope_too_large"
    personal_reasons = "personal_reasons"
    not_available_capacity = "not_available_capacity"
    scope_not_in_skillset = "scope_not_in_skillset"
    deadline_not_work = "deadline_not_work"
    not_relevant_goals = "not_relevant_goals"
    other = "other"


class DataSensitivity(str, Enum):
    public = "PUBLIC"
    internal = "INTERNAL"
    confidential = "CONFIDENTIAL"
    restricted = "RESTRICTED"


class Seniority(str, Enum):
    fresher = "fresher"
    junior = "junior"
    mid = "mid"
    senior = "senior"
    lead = "lead"


class EffortFilter(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"


class DeadlineWithinDiscovery(str, Enum):
    week_1 = "week_1"
    weeks_2 = "weeks_2"
    month_1 = "month_1"


class UploadCategory(str, Enum):
    deliverable = "deliverable"
    reference = "reference"
    evidence = "evidence"
    draft = "draft"


class PricingModel(str, Enum):
    fixed = "fixed"
    hourly = "hourly"
    milestone = "milestone"


class Pricing(BaseModel):
    amount: float
    currency: str
    model: PricingModel


class TaskSummaryKPI(BaseModel):
    available: int
    in_progress: int
    submitted: int
    completed: int
    rework: int
    active_offers: int = 0


class TaskListItem(BaseModel):
    id: str
    title: str
    project_title: str
    milestone_title: str
    status: TaskStatus
    priority: TaskPriority
    skills_required: list[str]
    estimated_hours: float | None = None
    pricing: Pricing
    match_score: float | None = None
    match_reason: str | None = None
    due_date: date | None = None
    sla_deadline: datetime | None = None
    progress_percent: float | None = None
    hours_logged: float | None = None
    domain_tag: str | None = None
    seniority_required: Seniority | None = None
    contributor_seniority: Seniority | None = None
    skills_matched: list[str] = Field(default_factory=list)
    offer_expires_at: datetime | None = None
    offered_at: datetime | None = None
    data_sensitivity: DataSensitivity | None = None
    nda_required: bool = False
    effort_display: str | None = None


class ReferenceMaterial(BaseModel):
    id: str
    name: str
    url: str | None = None
    description: str | None = None


class TaskDetail(BaseModel):
    id: str
    project_id: str
    project_title: str
    milestone_title: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    skills_required: list[str]
    estimated_hours: float | None = None
    pricing: Pricing
    match_score: float | None = None
    match_reason: str | None = None
    due_date: date | None = None
    sla_deadline: datetime | None = None
    assigned_at: datetime | None = None
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    accepted_at: datetime | None = None
    review_score: float | None = None
    review_comment: str | None = None
    rework_reason: str | None = None
    rework_deadline: datetime | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    evidence_types_required: list[str] = Field(default_factory=list)
    milestone_number: int | None = None
    reference_materials: list[ReferenceMaterial] = Field(default_factory=list)
    reviewer_guidance_preview: str | None = None
    domain_tag: str | None = None
    seniority_required: Seniority | None = None
    contributor_seniority: Seniority | None = None
    skills_matched: list[str] = Field(default_factory=list)
    offer_expires_at: datetime | None = None
    offered_at: datetime | None = None
    data_sensitivity: DataSensitivity | None = None
    nda_required: bool = False
    effort_display: str | None = None


class PaginatedTasks(BaseModel):
    items: list[TaskListItem]
    page: int
    page_size: int
    total: int


class AcceptBody(BaseModel):
    accepted_at: datetime | None = None
    note: str | None = None


class DeclineBody(BaseModel):
    reason: DeclineReason | None = None
    notes: str | None = Field(None, max_length=200)

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            return None
        return v.strip() if v is not None else None


class DiscoverySummary(BaseModel):
    """§7.1 active offers badge — poll every ~60s from UI."""

    active_offers: int
    server_time: datetime


class AcceptImpactResponse(BaseModel):
    """§7.4 workload impact before confirming accept."""

    current_active_tasks: int
    hours_committed_this_week: float
    declared_hours_per_week: float
    task_estimated_hours: float
    after_accept_weekly_hours: float
    capacity_percent_after: float
    would_exceed_capacity: bool
    advisory_near_capacity: bool
    concurrent_deadlines_notice: str | None = None
    accept_allowed: bool


class StartBody(BaseModel):
    started_at: datetime | None = None


class RequestExtensionBody(BaseModel):
    requested_due_date: date
    reason: str
    notes: str | None = None
    supporting_attachment_ids: list[str] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    id: str
    event_type: str
    at: datetime
    label: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkroomTemplate(BaseModel):
    id: str
    name: str
    url: str | None = None
    description: str | None = None


class WorkroomLink(BaseModel):
    id: str
    title: str
    url: str
    description: str | None = None


class WorkroomUpload(BaseModel):
    id: str
    filename: str
    category: UploadCategory
    title: str | None = None
    description: str | None = None
    uploaded_at: datetime
    size_bytes: int | None = None


class QAMessage(BaseModel):
    id: str
    author: str
    message: str
    created_at: datetime
    attachment_ids: list[str] = Field(default_factory=list)


class EvidenceChecklistItem(BaseModel):
    id: str
    label: str
    completed: bool
    evidence_file_id: str | None = None
    notes: str | None = None


class WorkroomView(BaseModel):
    instructions: str
    templates: list[WorkroomTemplate]
    links: list[WorkroomLink]
    uploads: list[WorkroomUpload]
    qa_messages: list[QAMessage]
    evidence_checklist: list[EvidenceChecklistItem]
    progress_percent: float | None = None
    hours_logged: float | None = None
    last_activity_at: datetime | None = None


class PostWorkroomMessageBody(BaseModel):
    message: str
    attachment_ids: list[str] = Field(default_factory=list)


class PaginatedMessages(BaseModel):
    items: list[QAMessage]
    page: int
    page_size: int
    total: int


class UploadResponse(BaseModel):
    id: str
    filename: str
    category: UploadCategory
    title: str | None = None
    description: str | None = None
    uploaded_at: datetime


class ChecklistPatchBody(BaseModel):
    completed: bool
    evidence_file_id: str | None = None
    notes: str | None = None


class ActionAck(BaseModel):
    ok: bool = True
    message: str | None = None

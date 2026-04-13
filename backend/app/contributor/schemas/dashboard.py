from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ContributorMe(BaseModel):
    id: str
    display_name: str
    anonymous_id: str
    avatar: str | None
    email: str
    track: str
    designation: str
    seniority_level: str
    verification_status: Literal["unverified", "pending", "verified", "rejected"]
    timezone: str
    availability: str
    last_availability_updated_at: str | None
    profile_completeness: float
    onboarding_complete: bool
    assessment_status: Literal["none", "pending", "in_progress", "completed", "results_ready"]
    kyc_required: bool
    kyc_status: str | None


class DashboardKpi(BaseModel):
    key: str
    label: str
    value: str | int | float
    trend: Literal["up", "down", "flat"] | None = None


class ActiveTask(BaseModel):
    id: str
    title: str
    project_title: str | None = None
    milestone_title: str | None = None
    status: str
    due_at: str | None
    due_relative: str | None = None
    priority: str
    workroom_path: str | None = None


class EarningsSnapshot(BaseModel):
    currency: str
    earned_this_month: float
    total_paid_all_time: float
    pending_payout: float


ActionItemKind = Literal[
    "deadline_today",
    "deadline_tomorrow",
    "rework_required",
    "offer_expiring",
    "assessment_pending",
    "payment_ready",
]


class DashboardActionItem(BaseModel):
    id: str
    kind: ActionItemKind
    urgency: Literal["critical", "high", "medium", "low"]
    title: str
    subtitle: str | None = None
    task_id: str | None = None
    offer_id: str | None = None
    cta_label: str | None = None
    cta_href: str | None = None


class SystemBanner(BaseModel):
    id: str
    variant: Literal["amber", "red", "blue", "green"]
    title: str
    body: str
    cta_label: str | None = None
    cta_href: str | None = None
    dismissible: bool = True
    task_id: str | None = None


class RecentEarning(BaseModel):
    id: str
    amount: float
    currency: str
    label: str
    earned_at: str


class CredentialItem(BaseModel):
    id: str
    name: str
    issuer: str
    status: str
    expires_at: str | None


class SkillItem(BaseModel):
    id: str
    name: str
    level: str


class NotificationItem(BaseModel):
    id: str
    type: str
    title: str
    body: str
    read: bool
    created_at: str


class LearningItem(BaseModel):
    id: str
    title: str
    url: str
    duration_minutes: int
    reason: str


class ContributorDashboard(BaseModel):
    greeting_name: str
    kpis: list[DashboardKpi]
    earnings_snapshot: EarningsSnapshot
    action_items: list[DashboardActionItem]
    system_banners: list[SystemBanner]
    active_tasks: list[ActiveTask]
    recent_earnings: list[RecentEarning]
    credentials: list[CredentialItem]
    skills: list[SkillItem]
    notifications: list[NotificationItem]
    recommended_learning: list[LearningItem]


class NotificationReadPatch(BaseModel):
    """Body for PATCH …/notifications/{id}/read (default: mark as read)."""

    read: bool = True


class NotificationsListResponse(BaseModel):
    items: list[NotificationItem]
    page: int
    page_size: int
    total: int


class ReadAllResponse(BaseModel):
    updated: int

"""
Reviewer module request/response schemas.
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class EvidenceRecommendationType(str, Enum):
    ACCEPT = "ACCEPT"
    REWORK = "REWORK"


class EvidenceRecommendRequest(BaseModel):
    score: int = Field(..., ge=0, le=100)
    comment: str = Field(..., min_length=1, max_length=4000)
    recommendation: EvidenceRecommendationType


class ReviewerProjectItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    status: str
    assigned_at: Optional[str] = None
    task_kind: Optional[str] = Field(default=None, alias="taskKind")
    related_id: Optional[str] = Field(default=None, alias="relatedId")
    notes: Optional[str] = None


class ReviewerDashboardData(BaseModel):
    """Shape of ``data`` on ``GET /reviewer/dashboard``."""

    model_config = ConfigDict(populate_by_name=True)

    assigned_task_count: int = Field(alias="assignedTaskCount")
    pending_evidence_reviews: int = Field(alias="pendingEvidenceReviews", default=0)
    completed_last_30_days: int = Field(default=0, alias="completedLast30Days")
    evidence_recommendations_accept: int = Field(default=0, alias="evidenceRecommendationsAccept")
    evidence_recommendations_rework: int = Field(default=0, alias="evidenceRecommendationsRework")
    evidence_approval_rate_percent: Optional[int] = Field(
        default=None,
        alias="evidenceApprovalRatePercent",
        description="ACCEPT / (ACCEPT+REWORK) * 100 when at least one recommendation exists.",
    )


class EvidenceRecommendResult(BaseModel):
    evidence_id: str = Field(alias="evidenceId")
    score: int
    recommendation: str

    model_config = ConfigDict(populate_by_name=True)


class CreateReviewerAssignmentRequest(BaseModel):
    """Admin creates a row in the reviewer work queue."""

    title: str = Field(..., min_length=1, max_length=300)
    task_kind: str = Field(
        default="other",
        validation_alias=AliasChoices("task_kind", "taskKind"),
    )
    related_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("related_id", "relatedId"),
    )
    notes: Optional[str] = Field(default=None, max_length=2000)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("task_kind")
    @classmethod
    def task_kind_allowed(cls, v: str) -> str:
        allowed = frozenset({"project", "evidence_review", "other"})
        key = (v or "other").strip().lower()
        if key not in allowed:
            raise ValueError(f'task_kind must be one of: {", ".join(sorted(allowed))}')
        return key


class UpdateReviewerAssignmentStatusRequest(BaseModel):
    """Reviewer updates queue row status (not for completing evidence reviews — use recommend)."""

    status: Literal["pending", "in_progress", "completed"]
    model_config = ConfigDict(populate_by_name=True)

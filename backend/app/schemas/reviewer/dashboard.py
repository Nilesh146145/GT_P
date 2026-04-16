from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReviewerDashboardData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assigned_task_count: int = Field(alias="assignedTaskCount")
    pending_evidence_reviews: int = Field(default=0, alias="pendingEvidenceReviews")
    completed_last_30_days: int = Field(default=0, alias="completedLast30Days")
    evidence_recommendations_accept: int = Field(default=0, alias="evidenceRecommendationsAccept")
    evidence_recommendations_rework: int = Field(default=0, alias="evidenceRecommendationsRework")
    evidence_approval_rate_percent: Optional[int] = Field(
        default=None,
        alias="evidenceApprovalRatePercent",
    )


from __future__ import annotations

from app.schemas.reviewer.assignment import (
    CreateReviewerAssignmentRequest,
    ReviewerProjectItem,
    UpdateReviewerAssignmentStatusRequest,
)
from app.schemas.reviewer.auth import ReviewerAuthState
from app.schemas.reviewer.dashboard import ReviewerDashboardData
from app.schemas.reviewer.evidence import (
    EvidenceRecommendRequest,
    EvidenceRecommendResult,
    EvidenceRecommendationType,
)
from app.schemas.reviewer.reviewer_user import (
    CreateReviewerRequest,
    CreateReviewerResponse,
    CreateReviewerUserApiResponse,
    ReviewerLifecycleStatus,
)


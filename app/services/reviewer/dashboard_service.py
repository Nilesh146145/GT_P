from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.database import (
    get_reviewer_assignments_collection,
    get_reviewer_recommendations_collection,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def get_dashboard(reviewer_user_id: str) -> dict[str, int | None]:
    assignments_col = get_reviewer_assignments_collection()
    recommendations_col = get_reviewer_recommendations_collection()
    since = _utc_now() - timedelta(days=30)

    assigned_task_count = await assignments_col.count_documents(
        {"reviewer_user_id": reviewer_user_id, "status": {"$ne": "completed"}}
    )
    pending_evidence_reviews = await assignments_col.count_documents(
        {
            "reviewer_user_id": reviewer_user_id,
            "task_kind": "evidence_review",
            "status": {"$in": ["pending", "in_progress"]},
        }
    )
    completed_last_30_days = await assignments_col.count_documents(
        {
            "reviewer_user_id": reviewer_user_id,
            "status": "completed",
            "updated_at": {"$gte": since},
        }
    )
    accepted = await recommendations_col.count_documents(
        {"reviewer_user_id": reviewer_user_id, "recommendation": "ACCEPT"}
    )
    rework = await recommendations_col.count_documents(
        {"reviewer_user_id": reviewer_user_id, "recommendation": "REWORK"}
    )

    total = accepted + rework
    approval_rate: Optional[int] = None
    if total:
        approval_rate = int(round((accepted / total) * 100))

    return {
        "assignedTaskCount": assigned_task_count,
        "pendingEvidenceReviews": pending_evidence_reviews,
        "completedLast30Days": completed_last_30_days,
        "evidenceRecommendationsAccept": accepted,
        "evidenceRecommendationsRework": rework,
        "evidenceApprovalRatePercent": approval_rate,
    }


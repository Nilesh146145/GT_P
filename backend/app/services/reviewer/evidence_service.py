from __future__ import annotations

from datetime import datetime, timezone

from app.core.database import (
    get_reviewer_assignments_collection,
    get_reviewer_evidence_collection,
    get_reviewer_recommendations_collection,
)
from app.schemas.reviewer.evidence import EvidenceRecommendRequest


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def recommend_evidence(
    evidence_id: str,
    body: EvidenceRecommendRequest,
    reviewer_user_id: str,
) -> dict[str, int | str]:
    now = _utc_now()
    recommendation_doc = {
        "evidence_id": evidence_id,
        "reviewer_user_id": reviewer_user_id,
        "score": body.score,
        "comment": body.comment.strip(),
        "recommendation": body.recommendation.value,
        "created_at": now,
    }
    await get_reviewer_recommendations_collection().insert_one(recommendation_doc)
    await get_reviewer_evidence_collection().update_many(
        {"reviewer_user_id": reviewer_user_id, "evidence_id": evidence_id},
        {
            "$set": {
                "status": "completed",
                "score": body.score,
                "comment": body.comment.strip(),
                "recommendation": body.recommendation.value,
                "updated_at": now,
            }
        },
    )
    await get_reviewer_assignments_collection().update_many(
        {
            "reviewer_user_id": reviewer_user_id,
            "task_kind": "evidence_review",
            "related_id": evidence_id,
            "status": {"$in": ["pending", "in_progress"]},
        },
        {"$set": {"status": "completed", "updated_at": now}},
    )
    return {
        "evidenceId": evidence_id,
        "score": body.score,
        "recommendation": body.recommendation.value,
    }


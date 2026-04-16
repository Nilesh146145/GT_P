"""
Reviewer dashboard and evidence recommendation persistence (MongoDB via Motor).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException

from app.core.database import (
    get_evidence_recommendations_collection,
    get_reviewer_assignments_collection,
    get_users_collection,
)
from app.schemas.reviewer import (
    CreateReviewerAssignmentRequest,
    EvidenceRecommendRequest,
    UpdateReviewerAssignmentStatusRequest,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid id format")


async def create_assignment(
    reviewer_user_id: str,
    body: CreateReviewerAssignmentRequest,
    admin_user_id: str,
) -> dict[str, Any]:
    """Create a reviewer queue row. Caller must enforce admin role."""
    users = get_users_collection()
    rid = _oid(reviewer_user_id)
    reviewer = await users.find_one({"_id": rid})
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer user not found")
    role = (reviewer.get("role") or "").strip().lower()
    if role != "reviewer":
        raise HTTPException(status_code=400, detail="Target user is not a reviewer")

    col = get_reviewer_assignments_collection()
    doc = {
        "reviewer_user_id": reviewer_user_id,
        "title": body.title.strip(),
        "task_kind": body.task_kind,
        "related_id": (body.related_id or "").strip() or None,
        "notes": (body.notes or "").strip() or None,
        "status": "pending",
        "assigned_by_user_id": admin_user_id,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }
    result = await col.insert_one(doc)
    return {
        "id": str(result.inserted_id),
        "reviewer_user_id": reviewer_user_id,
        "title": doc["title"],
        "task_kind": doc["task_kind"],
        "related_id": doc["related_id"],
        "status": doc["status"],
    }


async def get_dashboard(reviewer_user_id: str) -> dict[str, Any]:
    """Aggregate queue size, evidence pending count, recent completions, and recommendation mix."""
    assign_col = get_reviewer_assignments_collection()
    ev_col = get_evidence_recommendations_collection()
    since = _utc_now() - timedelta(days=30)

    assigned_task_count = await assign_col.count_documents(
        {"reviewer_user_id": reviewer_user_id, "status": {"$ne": "completed"}}
    )
    pending_evidence_reviews = await assign_col.count_documents(
        {
            "reviewer_user_id": reviewer_user_id,
            "task_kind": "evidence_review",
            "status": {"$in": ["pending", "in_progress"]},
        }
    )
    completed_last_30_days = await assign_col.count_documents(
        {
            "reviewer_user_id": reviewer_user_id,
            "status": "completed",
            "updated_at": {"$gte": since},
        }
    )
    acc = await ev_col.count_documents(
        {"reviewer_user_id": reviewer_user_id, "recommendation": "ACCEPT"}
    )
    rew = await ev_col.count_documents(
        {"reviewer_user_id": reviewer_user_id, "recommendation": "REWORK"}
    )
    total_rec = acc + rew
    rate: Optional[int] = None
    if total_rec > 0:
        rate = int(round(100 * acc / total_rec))

    return {
        "assignedTaskCount": assigned_task_count,
        "pendingEvidenceReviews": pending_evidence_reviews,
        "completedLast30Days": completed_last_30_days,
        "evidenceRecommendationsAccept": acc,
        "evidenceRecommendationsRework": rew,
        "evidenceApprovalRatePercent": rate,
    }


async def list_assigned_projects(reviewer_user_id: str) -> list[dict[str, Any]]:
    """Return this reviewer's assignment queue (newest first)."""
    col = get_reviewer_assignments_collection()
    cursor = (
        col.find({"reviewer_user_id": reviewer_user_id})
        .sort("created_at", -1)
        .limit(200)
    )
    out: list[dict[str, Any]] = []
    async for doc in cursor:
        out.append(_assignment_to_dict(doc))
    return out


async def update_assignment_status(
    reviewer_user_id: str,
    assignment_id: str,
    body: UpdateReviewerAssignmentStatusRequest,
) -> dict[str, Any]:
    """
    Update status on the reviewer's own assignment.

    ``evidence_review`` rows cannot be marked ``completed`` here — use
    ``submit_evidence_recommendation`` (which completes matching rows).
    """
    col = get_reviewer_assignments_collection()
    aid = _oid(assignment_id)
    doc = await col.find_one({"_id": aid, "reviewer_user_id": reviewer_user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Assignment not found")

    new_status = body.status
    cur = (doc.get("status") or "pending").strip().lower()
    tk = (doc.get("task_kind") or "other").strip().lower()

    if new_status == cur:
        return _assignment_to_dict(doc)

    if cur == "completed":
        raise HTTPException(status_code=400, detail="Assignment is already completed.")

    if new_status == "completed" and tk == "evidence_review":
        raise HTTPException(
            status_code=400,
            detail="Complete evidence reviews via POST /api/v1/reviewer/evidence/{evidence_id}/recommend.",
        )

    if new_status == "in_progress" and cur != "pending":
        raise HTTPException(
            status_code=400,
            detail="Can only move to in_progress from pending.",
        )

    if new_status == "completed" and cur not in ("pending", "in_progress"):
        raise HTTPException(status_code=400, detail="Invalid status transition.")

    if new_status == "pending":
        raise HTTPException(
            status_code=400,
            detail="Cannot move assignment back to pending.",
        )

    now = _utc_now()
    await col.update_one(
        {"_id": aid},
        {"$set": {"status": new_status, "updated_at": now}},
    )
    updated = await col.find_one({"_id": aid})
    assert updated is not None
    return _assignment_to_dict(updated)


def _assignment_to_dict(doc: dict[str, Any]) -> dict[str, Any]:
    created = doc.get("created_at")
    assigned_at: Optional[str] = None
    if isinstance(created, datetime):
        assigned_at = created.isoformat()
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title") or "",
        "status": doc.get("status") or "pending",
        "assignedAt": assigned_at,
        "taskKind": doc.get("task_kind"),
        "relatedId": doc.get("related_id"),
        "notes": doc.get("notes"),
    }


async def submit_evidence_recommendation(
    evidence_id: str,
    body: EvidenceRecommendRequest,
    reviewer_user_id: str,
) -> dict[str, Any]:
    """Persist recommendation and mark matching evidence_review assignments completed."""
    ev_col = get_evidence_recommendations_collection()
    assign_col = get_reviewer_assignments_collection()
    now = _utc_now()
    rec_doc = {
        "evidence_id": evidence_id,
        "reviewer_user_id": reviewer_user_id,
        "score": body.score,
        "comment": body.comment.strip(),
        "recommendation": body.recommendation.value,
        "created_at": now,
    }
    await ev_col.insert_one(rec_doc)

    await assign_col.update_many(
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
        "recommendation": rec_doc["recommendation"],
    }

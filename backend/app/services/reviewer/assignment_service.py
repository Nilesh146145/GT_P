from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.core.database import (
    get_reviewer_assignments_collection,
    get_reviewer_evidence_collection,
    get_reviewer_projects_collection,
    get_users_collection,
)
from app.models.reviewer import ReviewerTaskKind
from app.schemas.reviewer.assignment import (
    CreateReviewerAssignmentRequest,
    UpdateReviewerAssignmentStatusRequest,
)
from app.services.reviewer import reviewer_auth_service


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid id format") from exc


def _assignment_to_dict(document: dict[str, Any]) -> dict[str, Any]:
    created = document.get("created_at")
    assigned_at: Optional[str] = None
    if isinstance(created, datetime):
        assigned_at = created.isoformat()
    return {
        "id": str(document["_id"]),
        "title": document.get("title") or "",
        "status": document.get("status") or "pending",
        "assignedAt": assigned_at,
        "taskKind": document.get("task_kind"),
        "relatedId": document.get("related_id"),
        "notes": document.get("notes"),
    }


async def _sync_project_shadow(assignment_id: str, doc: dict[str, Any], now: datetime) -> None:
    if doc.get("task_kind") != ReviewerTaskKind.PROJECT.value:
        return
    await get_reviewer_projects_collection().update_one(
        {"assignment_id": assignment_id},
        {
            "$set": {
                "assignment_id": assignment_id,
                "reviewer_user_id": doc["reviewer_user_id"],
                "project_id": doc.get("related_id"),
                "title": doc["title"],
                "status": doc["status"],
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


async def _sync_evidence_shadow(assignment_id: str, doc: dict[str, Any], now: datetime) -> None:
    if doc.get("task_kind") != ReviewerTaskKind.EVIDENCE_REVIEW.value or not doc.get("related_id"):
        return
    await get_reviewer_evidence_collection().update_one(
        {"assignment_id": assignment_id},
        {
            "$set": {
                "assignment_id": assignment_id,
                "reviewer_user_id": doc["reviewer_user_id"],
                "evidence_id": doc["related_id"],
                "title": doc["title"],
                "status": doc["status"],
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


async def create_assignment(
    reviewer_user_id: str,
    body: CreateReviewerAssignmentRequest,
    actor_user_id: str,
) -> dict[str, Any]:
    reviewer = await get_users_collection().find_one({"_id": _oid(reviewer_user_id)})
    if not reviewer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewer user not found")
    if not reviewer_auth_service.is_reviewer_role(reviewer.get("role")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target user is not a reviewer")

    now = _utc_now()
    document = {
        "reviewer_user_id": reviewer_user_id,
        "title": body.title.strip(),
        "task_kind": body.task_kind,
        "related_id": (body.related_id or "").strip() or None,
        "notes": (body.notes or "").strip() or None,
        "status": "pending",
        "assigned_by_user_id": actor_user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await get_reviewer_assignments_collection().insert_one(document)
    assignment_id = str(result.inserted_id)
    await _sync_project_shadow(assignment_id, document, now)
    await _sync_evidence_shadow(assignment_id, document, now)
    return {
        "id": assignment_id,
        "reviewer_user_id": reviewer_user_id,
        "title": document["title"],
        "task_kind": document["task_kind"],
        "related_id": document["related_id"],
        "status": document["status"],
    }


async def list_assignments(reviewer_user_id: str) -> list[dict[str, Any]]:
    cursor = (
        get_reviewer_assignments_collection()
        .find({"reviewer_user_id": reviewer_user_id})
        .sort("created_at", -1)
        .limit(200)
    )
    items: list[dict[str, Any]] = []
    async for row in cursor:
        items.append(_assignment_to_dict(row))
    return items


async def update_assignment_status(
    reviewer_user_id: str,
    assignment_id: str,
    body: UpdateReviewerAssignmentStatusRequest,
) -> dict[str, Any]:
    assignments_col = get_reviewer_assignments_collection()
    object_id = _oid(assignment_id)
    document = await assignments_col.find_one({"_id": object_id, "reviewer_user_id": reviewer_user_id})
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    current_status = (document.get("status") or "pending").strip().lower()
    task_kind = (document.get("task_kind") or "other").strip().lower()
    new_status = body.status

    if new_status == current_status:
        return _assignment_to_dict(document)
    if current_status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignment is already completed.")
    if new_status == "completed" and task_kind == ReviewerTaskKind.EVIDENCE_REVIEW.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete evidence reviews via POST /api/v1/reviewer/evidence/{evidence_id}/recommend.",
        )
    if new_status == "in_progress" and current_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only move to in_progress from pending.",
        )
    if new_status == "completed" and current_status not in ("pending", "in_progress"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status transition.")
    if new_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot move assignment back to pending.",
        )

    now = _utc_now()
    await assignments_col.update_one(
        {"_id": object_id},
        {"$set": {"status": new_status, "updated_at": now}},
    )
    updated = await assignments_col.find_one({"_id": object_id})
    assert updated is not None
    await _sync_project_shadow(assignment_id, updated, now)
    await _sync_evidence_shadow(assignment_id, updated, now)
    return _assignment_to_dict(updated)


"""Plan Review page, revision modal context, and revised-plan diff (DCP-007: vs previous revision)."""

from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

from app.core.database import is_db_connected
from app.models.decomposition import PlanReviewPageResponse, PlanStatus, PlanSummaryStrip, ReviewChecklistItem, RevisionRound
from app.schemas.decomposition.revision import RevisionNotesRequest
from app.services.decomposition import checklist_service, plan_repository, plan_service

_DCP005 = "This project has not been kicked off yet."


async def _load(enterprise_profile_id: str, plan_id: str) -> dict:
    if not is_db_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    doc = await plan_repository.find_by_plan_id(plan_id)
    if doc is None or doc.get("enterprise_profile_id") != enterprise_profile_id:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")
    if not doc.get("kicked_off") or doc.get("status") == "PENDING_KICKOFF":
        raise HTTPException(status_code=403, detail=_DCP005)
    return doc


def _revision_round_enum(used: int) -> RevisionRound:
    order = (RevisionRound.ROUND_0, RevisionRound.ROUND_1, RevisionRound.ROUND_2, RevisionRound.ROUND_3)
    return order[min(max(used, 0), 3)]


def _revision_warning_next_submit(used: int) -> str | None:
    """Banner when about to submit another revision (used = already completed requests)."""
    if used == 1:
        return "This is your second revision. One revision round remains after this."
    if used == 2:
        return "This is your final revision. If the revised plan still does not meet your needs, GlimmoraTeam Admin will be notified to assist."
    return None


async def get_plan_review_page(enterprise_profile_id: str, plan_id: str) -> PlanReviewPageResponse:
    doc = await _load(enterprise_profile_id, plan_id)
    used = int(doc.get("revision_requests_used") or 0)
    st = str(doc.get("status") or "")
    summary = plan_service.summary_block(doc)
    strip = PlanSummaryStrip(
        total_milestones=summary["total_milestones"],
        total_tasks=summary["total_tasks"],
        estimated_effort_days=summary["estimated_total_effort_days"],
        project_start=str(summary["project_start"]),
        project_end=str(summary["project_end"]),
        critical_path_tasks=summary["critical_path_task_count"],
    )
    c = doc.get("checklist") or {"item1": False, "item2": False, "item3": False}
    checklist = [
        ReviewChecklistItem(
            item_id="item1",
            label=checklist_service.REVIEW_LABELS["item1"],
            is_checked=bool(c.get("item1")),
        ),
        ReviewChecklistItem(
            item_id="item2",
            label=checklist_service.REVIEW_LABELS["item2"],
            is_checked=bool(c.get("item2")),
        ),
        ReviewChecklistItem(
            item_id="item3",
            label=checklist_service.REVIEW_LABELS["item3"],
            is_checked=bool(c.get("item3")),
        ),
    ]
    all_checked = bool(c.get("item1") and c.get("item2") and c.get("item3"))
    can_rev = st == "PLAN_REVIEW_REQUIRED" and used < plan_service.MAX_REVISION_ROUNDS
    can_confirm = st == "PLAN_REVIEW_REQUIRED" and all_checked
    try:
        plan_status = PlanStatus(st)
    except ValueError:
        plan_status = PlanStatus.NEW
    max_reached = used >= plan_service.MAX_REVISION_ROUNDS
    return PlanReviewPageResponse(
        plan_id=plan_id,
        project_name=str(doc.get("project_name") or ""),
        sow_reference=str(doc.get("sow_reference") or ""),
        plan_version=str((doc.get("plan_content") or {}).get("plan_version") or 1),
        status=plan_status,
        revision_round=_revision_round_enum(used),
        revision_label=f"Revision {used} of {plan_service.MAX_REVISION_ROUNDS}",
        max_revisions_reached=max_reached,
        revision_warning=(
            "Maximum revisions reached — GlimmoraTeam Admin has been notified."
            if max_reached and doc.get("admin_notified_max_revision")
            else None
        ),
        can_request_revision=can_rev,
        can_confirm_plan=can_confirm,
        revision_in_progress=st == "REVISION_IN_PROGRESS",
        summary=strip,
        checklist=checklist,
        checklist_complete=all_checked,
    )


async def get_revision_modal(enterprise_profile_id: str, plan_id: str) -> dict:
    doc = await _load(enterprise_profile_id, plan_id)
    used = int(doc.get("revision_requests_used") or 0)
    st = str(doc.get("status") or "")
    flagged = await plan_service.apply_flagged_tasks_for_revision_notes(plan_id, enterprise_profile_id)
    next_round = min(used + 1, plan_service.MAX_REVISION_ROUNDS)
    return {
        "revision_count": used,
        "next_revision_round": next_round,
        "max_revisions": plan_service.MAX_REVISION_ROUNDS,
        "status": st,
        "flagged_tasks": flagged,
        "revision_warning_banner": _revision_warning_next_submit(used),
        "can_submit_revision": st == "PLAN_REVIEW_REQUIRED" and used < plan_service.MAX_REVISION_ROUNDS,
    }


async def request_revision(enterprise_profile_id: str, plan_id: str, data: RevisionNotesRequest) -> dict:
    from app.models.decomposition import RevisionRequest

    body = RevisionRequest(requested_by="enterprise", revision_notes=data.notes)
    return await plan_service.request_plan_revision(enterprise_profile_id, plan_id, body)


def _calculate_diff(old_tasks: list[dict], new_tasks: list[dict]) -> tuple[list[int], list[int], list[int]]:
    old_map = {int(t["id"]): t for t in old_tasks if t.get("id") is not None}
    new_map = {int(t["id"]): t for t in new_tasks if t.get("id") is not None}

    added: list[int] = []
    modified: list[int] = []
    removed: list[int] = []

    for task_id, task in new_map.items():
        if task_id not in old_map:
            added.append(task_id)
        elif task != old_map[task_id]:
            modified.append(task_id)

    for task_id in old_map:
        if task_id not in new_map:
            removed.append(task_id)

    return added, modified, removed


async def get_revised_plan(enterprise_profile_id: str, plan_id: str) -> dict:
    doc = await _load(enterprise_profile_id, plan_id)
    versions = list(doc.get("revision_snapshots") or [])
    if len(versions) < 2:
        raise HTTPException(status_code=400, detail="No revision comparison available (need at least two plan snapshots).")

    latest = versions[-1]
    previous = versions[-2]
    old_tasks = list(previous.get("tasks") or [])
    new_tasks = list(latest.get("tasks") or [])
    added, modified, removed = _calculate_diff(old_tasks, new_tasks)

    return {
        "current_revision": latest.get("revision_index", len(versions) - 1),
        "tasks": deepcopy(new_tasks),
        "changes": {"added": added, "modified": modified, "removed": removed},
        "summary": {"added": len(added), "modified": len(modified), "removed": len(removed)},
        "revision_notes": latest.get("notes"),
    }


async def get_revision_detail(enterprise_profile_id: str, plan_id: str, revision_id: int) -> dict:
    doc = await _load(enterprise_profile_id, plan_id)
    for version in doc.get("revision_snapshots") or []:
        if int(version.get("revision_index", -1)) == revision_id:
            return {
                "revision_id": revision_id,
                "notes": version.get("notes") or "",
                "tasks": deepcopy(version.get("tasks") or []),
            }
    raise HTTPException(status_code=404, detail="Revision not found")

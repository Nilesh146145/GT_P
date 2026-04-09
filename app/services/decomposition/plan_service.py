"""Enterprise decomposition plan lifecycle: §8 kick-off gate, confirm, revision, lock (Mongo-backed)."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.database import is_db_connected
from app.models.decomposition import (
    ConfirmPlanRequest,
    CreateDecompositionPlanRequest,
    LockPlanRequest,
    PlanStatus,
    RevisionRequest,
)
from app.schemas.decomposition.plans import (
    ChecklistStatusResponse,
    PlanStateResponse,
    RevisionCounterResponse,
    SummaryResponse,
)
from app.services.decomposition import plan_repository
from app.services.decomposition.plan_template import build_new_plan_document, default_task_details, default_task_list

logger = logging.getLogger(__name__)

MAX_REVISION_ROUNDS = 3
DCP003_MSG = "Please provide at least 30 characters describing what needs to change."
DCP005_MSG = "This project has not been kicked off yet."


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_db() -> None:
    if not is_db_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")


def _days_plan_exceeds_sow(doc: dict[str, Any]) -> int | None:
    try:
        pe = date.fromisoformat(str(doc.get("plan_end", ""))[:10])
        se = date.fromisoformat(str(doc.get("sow_end", ""))[:10])
        delta = (pe - se).days
        return max(0, delta) if delta > 0 else 0
    except (TypeError, ValueError):
        return None


def _plan_exceeds_sow_warning_message(doc: dict[str, Any]) -> str | None:
    d = _days_plan_exceeds_sow(doc)
    if d and d > 0:
        return f"Plan end date exceeds SOW committed end date by {d} days."
    return None


def _iso_field(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def summary_block(doc: dict[str, Any]) -> dict[str, Any]:
    tasks = doc.get("task_list") or []
    milestones = {t.get("milestone") for t in tasks if isinstance(t, dict)}
    total_effort = sum(int(t.get("effort", 0) or 0) for t in tasks if isinstance(t, dict))
    crit = [t for t in tasks if isinstance(t, dict) and t.get("critical")]
    return {
        "total_milestones": len(milestones),
        "total_tasks": len(tasks),
        "estimated_total_effort_days": total_effort,
        "project_start": doc.get("plan_start") or "",
        "project_end": doc.get("plan_end") or "",
        "critical_path_task_count": len(crit),
    }


def _dashboard_message(status: str) -> str:
    return {
        "PENDING_KICKOFF": "Plan pending kick-off.",
        "PLAN_REVIEW_REQUIRED": "Plan review required — confirm or request a revision.",
        "REVISION_IN_PROGRESS": "Revision in progress — plan is read-only until AGI completes.",
        "PLAN_CONFIRMED": "Plan confirmed — contributor matching in progress.",
        "PLAN_LOCKED": "Plan locked — delivery started.",
    }.get(status, "Unknown plan state.")


def _list_row_flags(status: str) -> tuple[bool, bool, str | None]:
    """is_read_only, is_urgent, revision_estimated_minutes."""
    if status == "PLAN_REVIEW_REQUIRED":
        return False, True, None
    if status == "REVISION_IN_PROGRESS":
        return True, False, "15-60 min"
    if status in ("PLAN_CONFIRMED", "PLAN_LOCKED"):
        return True, False, None
    return True, False, None


def _status_enum(raw: str) -> PlanStatus:
    try:
        return PlanStatus(raw)
    except ValueError:
        return PlanStatus.NEW


async def _get_owned_plan(plan_id: str, enterprise_profile_id: str) -> dict[str, Any]:
    doc = await plan_repository.find_by_plan_id(plan_id)
    if doc is None or doc.get("enterprise_profile_id") != enterprise_profile_id:
        raise HTTPException(
            status_code=404,
            detail={"error": "Plan not found", "plan_id": plan_id, "message": f"No plan with ID '{plan_id}' exists."},
        )
    return doc


async def _get_owned_plan_for_status_string(plan_id: str, enterprise_profile_id: str) -> dict[str, Any]:
    try:
        return await _get_owned_plan(plan_id, enterprise_profile_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.") from exc
        raise


def _assert_kicked_off(doc: dict[str, Any]) -> None:
    if not doc.get("kicked_off") or doc.get("status") == "PENDING_KICKOFF":
        raise HTTPException(status_code=403, detail=DCP005_MSG)


def _doc_to_plan_response(doc: dict[str, Any]) -> dict[str, Any]:
    st = doc.get("status", "")
    content = doc.get("plan_content") or {}
    used = int(doc.get("revision_requests_used") or 0)
    summary = summary_block(doc)
    is_read_only, is_urgent, rev_est = _list_row_flags(st)
    exceed = _days_plan_exceeds_sow(doc)
    return {
        "plan_id": doc["plan_id"],
        "project_name": doc.get("project_name") or "",
        "project_description": content.get("project_description") or "",
        "sow_reference": doc.get("sow_reference") or "",
        "plan_version": int(content.get("plan_version") or 1),
        "status": _status_enum(st),
        "dashboard_message": _dashboard_message(st),
        "is_read_only": is_read_only,
        "is_urgent": is_urgent,
        "revision_count": used,
        "max_revisions": MAX_REVISION_ROUNDS,
        "revision_limit_reached": used >= MAX_REVISION_ROUNDS,
        "revision_estimated_minutes": rev_est,
        "revision_requested_at": _iso_field(doc.get("revision_requested_at")),
        "confirmed_at": _iso_field(doc.get("confirmed_at")),
        "locked_at": _iso_field(doc.get("locked_at")),
        "locked_by_contributor_id": doc.get("locked_by_contributor_id"),
        "summary": summary,
        "objective": content.get("objective") or "",
        "scope": content.get("scope") or "",
        "total_duration_weeks": int(content.get("total_duration_weeks") or 0),
        "phases": content.get("phases") or [],
        "risks": content.get("risks") or [],
        "budget": content.get("budget") or {},
        "success_metrics": content.get("success_metrics") or [],
        "assumptions": content.get("assumptions") or [],
        "agi_confidence_score": float(content.get("agi_confidence_score") or 0.0),
        "generated_by": content.get("generated_by") or "",
        "generated_at": content.get("generated_at") or "",
        "enterprise_deadline_to_confirm": content.get("enterprise_deadline_to_confirm") or "",
        "plan_exceeds_sow_by_days": exceed if exceed and exceed > 0 else None,
    }


def _doc_to_plan_status_row(doc: dict[str, Any]) -> dict[str, Any]:
    st = doc.get("status", "")
    tasks = doc.get("task_list") or []
    milestones = {t.get("milestone") for t in tasks if isinstance(t, dict)}
    is_read_only, is_urgent, rev_est = _list_row_flags(st)
    exceed = _days_plan_exceeds_sow(doc)
    return {
        "plan_id": doc["plan_id"],
        "project_name": doc.get("project_name") or "",
        "status": _status_enum(st),
        "dashboard_message": _dashboard_message(st),
        "is_read_only": is_read_only,
        "is_urgent": is_urgent,
        "revision_estimated_minutes": rev_est,
        "sow_reference": doc.get("sow_reference"),
        "sow_version": str(doc.get("sow_version") or ""),
        "milestone_count": len(milestones),
        "task_count": len(tasks),
        "plan_exceeds_sow_by_days": exceed if exceed and exceed > 0 else None,
    }


async def create_plan(current_user: dict, body: CreateDecompositionPlanRequest) -> dict[str, Any]:
    """Insert PENDING_KICKOFF plan (enterprise scoped)."""
    _require_db()
    eid = current_user.get("enterprise_profile_id")
    if not eid:
        raise HTTPException(status_code=403, detail="Enterprise profile is required.")
    plan_id = str(uuid.uuid4())
    uid = str(current_user.get("id") or "")
    doc = build_new_plan_document(
        plan_id=plan_id,
        enterprise_profile_id=str(eid),
        created_by_user_id=uid,
        project_name=body.project_name,
        sow_reference=body.sow_reference,
        sow_version=body.sow_version,
        sow_start=body.sow_start,
        sow_end=body.sow_end,
    )
    await plan_repository.insert_plan(doc)
    return {"plan_id": plan_id, "status": PlanStatus.PENDING_KICKOFF, "message": "Plan stored; kick off to release to reviewers."}


async def list_plans_for_enterprise(current_user: dict) -> list[dict[str, Any]]:
    _require_db()
    eid = current_user.get("enterprise_profile_id")
    if not eid:
        raise HTTPException(status_code=403, detail="Enterprise profile is required.")
    rows = await plan_repository.list_kicked_off_for_enterprise(str(eid))
    return [_doc_to_plan_status_row(d) for d in rows]


async def get_plan(enterprise_profile_id: str, plan_id: str) -> dict[str, Any]:
    _require_db()
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    return _doc_to_plan_response(doc)


async def get_plan_status(enterprise_profile_id: str, plan_id: str) -> dict[str, Any]:
    _require_db()
    doc = await _get_owned_plan_for_status_string(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    return _doc_to_plan_status_row(doc)


async def confirm_plan(enterprise_profile_id: str, plan_id: str, body: ConfirmPlanRequest) -> dict[str, Any]:
    _require_db()
    _ = body  # acknowledged_by tracked client-side; server enforces checklist (DCP-001)
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    st = doc.get("status")
    if st == "PLAN_LOCKED":
        raise HTTPException(status_code=400, detail="Plan is locked; changes require a Change Request.")
    if st == "PLAN_CONFIRMED":
        raise HTTPException(status_code=400, detail="Plan already confirmed; this action cannot be undone (DCP-002).")
    if st == "REVISION_IN_PROGRESS":
        raise HTTPException(status_code=400, detail="Cannot confirm while a revision is in progress.")
    if st != "PLAN_REVIEW_REQUIRED":
        raise HTTPException(status_code=400, detail="Plan is not awaiting confirmation.")

    checklist = doc.get("checklist") or {}
    if not (checklist.get("item1") and checklist.get("item2") and checklist.get("item3")):
        raise HTTPException(
            status_code=400,
            detail="Complete all review checklist items before confirming the plan (DCP-001).",
        )

    updated = await plan_repository.find_one_and_update(
        {
            "plan_id": plan_id,
            "enterprise_profile_id": enterprise_profile_id,
            "kicked_off": True,
            "status": "PLAN_REVIEW_REQUIRED",
        },
        {"$set": {"status": "PLAN_CONFIRMED", "confirmed_at": _utc_iso()}},
    )
    if updated is None:
        raise HTTPException(status_code=409, detail="Plan state changed; refresh and try again.")
    return {
        "message": "Plan confirmed successfully.",
        "plan_id": plan_id,
        "new_status": PlanStatus.PLAN_CONFIRMED,
        "next_step": "Contributor matching is now running. Teams module will begin populating.",
    }


async def request_plan_revision(enterprise_profile_id: str, plan_id: str, body: RevisionRequest) -> dict[str, Any]:
    _require_db()
    if len(body.revision_notes.strip()) < 30:
        raise HTTPException(status_code=400, detail=DCP003_MSG)
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    st = doc.get("status")
    if st in ("PLAN_CONFIRMED", "PLAN_LOCKED"):
        raise HTTPException(status_code=400, detail="Revisions are not allowed after the plan is confirmed or locked.")
    if st == "REVISION_IN_PROGRESS":
        raise HTTPException(status_code=400, detail="A revision is already in progress.")
    if st != "PLAN_REVIEW_REQUIRED":
        raise HTTPException(status_code=400, detail="Plan is not in review.")

    used = int(doc.get("revision_requests_used") or 0)
    if used >= MAX_REVISION_ROUNDS:
        raise HTTPException(status_code=400, detail="Maximum revision rounds reached.")

    new_used = used + 1
    notify_admin = new_used == MAX_REVISION_ROUNDS
    if notify_admin:
        logger.warning(
            "DCP-004: Plan %s reached maximum revision rounds (%s); GlimmoraTeam Admin should be notified.",
            plan_id,
            MAX_REVISION_ROUNDS,
        )

    hist = list(doc.get("revision_history") or [])
    hist.append(
        {
            "requested_by": body.requested_by,
            "notes": body.revision_notes,
            "submitted_at": _utc_iso(),
            "round": new_used,
        }
    )

    await plan_repository.update_by_plan_id(
        plan_id,
        {
            "$set": {
                "status": "REVISION_IN_PROGRESS",
                "revision_requests_used": new_used,
                "last_revision_notes": body.revision_notes,
                "revision_history": hist,
                "revision_requested_at": _utc_iso(),
                "admin_notified_max_revision": bool(doc.get("admin_notified_max_revision")) or notify_admin,
                "flagged_task_ids": [],
            }
        },
    )

    return {
        "message": "Revision request submitted.",
        "plan_id": plan_id,
        "new_status": PlanStatus.REVISION_IN_PROGRESS,
        "estimated_revision": "15-60 min",
        "next_step": "Plan is read-only. Enterprise will be notified when revision is complete.",
        "revision_round": new_used,
        "admin_notified": notify_admin,
    }


async def lock_plan(enterprise_profile_id: str, plan_id: str, body: LockPlanRequest) -> dict[str, Any]:
    _require_db()
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    st = doc.get("status")
    if st == "PLAN_LOCKED":
        raise HTTPException(status_code=400, detail="Plan is already locked.")
    if st != "PLAN_CONFIRMED":
        raise HTTPException(status_code=400, detail="Plan must be CONFIRMED before locking.")

    updated = await plan_repository.find_one_and_update(
        {
            "plan_id": plan_id,
            "enterprise_profile_id": enterprise_profile_id,
            "kicked_off": True,
            "status": "PLAN_CONFIRMED",
        },
        {
            "$set": {
                "status": "PLAN_LOCKED",
                "locked_at": _utcnow(),
                "locked_by_contributor_id": body.contributor_id,
                "assignment_offer_id": body.assignment_offer_id,
            }
        },
    )
    if updated is None:
        raise HTTPException(status_code=409, detail="Plan state changed; refresh and try again.")
    return {
        "message": "Plan is now locked. Delivery has started.",
        "plan_id": plan_id,
        "new_status": PlanStatus.PLAN_LOCKED,
        "locked_by": body.contributor_id,
        "next_step": "Changes require a formal Change Request via Admin.",
    }


async def kickoff(enterprise_profile_id: str, plan_id: str) -> dict[str, Any]:
    _require_db()
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    if doc.get("withdrawn"):
        raise HTTPException(status_code=400, detail="Plan has been withdrawn.")
    if doc.get("kicked_off"):
        raise HTTPException(status_code=400, detail="Project is already kicked off.")
    if doc.get("status") != "PENDING_KICKOFF":
        raise HTTPException(status_code=400, detail="Plan is not pending kick-off.")

    await plan_repository.update_by_plan_id(
        plan_id,
        {
            "$set": {
                "kicked_off": True,
                "kicked_off_at": _utcnow(),
                "status": "PLAN_REVIEW_REQUIRED",
            }
        },
    )
    return {"message": "Plan released for enterprise review.", "plan_id": plan_id, "status": "PLAN_REVIEW_REQUIRED"}


async def withdraw_plan(enterprise_profile_id: str, plan_id: str) -> dict[str, Any]:
    _require_db()
    doc = await plan_repository.find_by_plan_id_include_withdrawn(plan_id)
    if doc is None or doc.get("enterprise_profile_id") != enterprise_profile_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    from app.core.database import get_decomposition_plans_collection

    col = get_decomposition_plans_collection()
    await col.update_one(
        {"plan_id": plan_id},
        {"$set": {"withdrawn": True, "updated_at": _utcnow()}},
    )
    return {"message": f"Plan {plan_id} withdrawn successfully", "status": "WITHDRAWN"}


async def get_revision(enterprise_profile_id: str, plan_id: str) -> RevisionCounterResponse:
    _require_db()
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    used = int(doc.get("revision_requests_used") or 0)
    return RevisionCounterResponse(plan_id=plan_id, revision=used)


async def get_summary(enterprise_profile_id: str, plan_id: str) -> SummaryResponse:
    _require_db()
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    s = summary_block(doc)
    return SummaryResponse(
        total_milestones=s["total_milestones"],
        total_tasks=s["total_tasks"],
        effort_days=s["estimated_total_effort_days"],
    )


async def get_status(enterprise_profile_id: str, plan_id: str) -> PlanStateResponse:
    _require_db()
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    return PlanStateResponse(status=str(doc.get("status") or ""))


async def get_checklist_status(enterprise_profile_id: str, plan_id: str) -> ChecklistStatusResponse:
    _require_db()
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    c = doc.get("checklist") or {"item1": False, "item2": False, "item3": False}
    return ChecklistStatusResponse(item1=bool(c.get("item1")), item2=bool(c.get("item2")), item3=bool(c.get("item3")))


async def confirm_plan_status(enterprise_profile_id: str, plan_id: str) -> dict[str, Any]:
    """Legacy path: same rules as confirm_plan without redundant body fields."""
    _require_db()
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    checklist = doc.get("checklist") or {}
    if not all((checklist.get("item1"), checklist.get("item2"), checklist.get("item3"))):
        raise HTTPException(status_code=400, detail="Checklist incomplete")
    if doc.get("status") != "PLAN_REVIEW_REQUIRED":
        raise HTTPException(status_code=400, detail="Plan is not awaiting confirmation.")
    return await confirm_plan(
        enterprise_profile_id,
        plan_id,
        ConfirmPlanRequest(confirmed_by=str(doc.get("created_by_user_id") or "enterprise")),
    )


async def get_lock_status(enterprise_profile_id: str, plan_id: str) -> dict[str, Any]:
    _require_db()
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    st = str(doc.get("status") or "")
    return {
        "plan_id": plan_id,
        "status": st,
        "is_locked": st == "PLAN_LOCKED",
        "can_request_revision": st not in ("PLAN_LOCKED", "PLAN_CONFIRMED", "REVISION_IN_PROGRESS"),
        "can_confirm": st == "PLAN_REVIEW_REQUIRED",
    }


class RevisionCompleteBody(BaseModel):
    """Optional payload when AGI finishes regenerating a plan."""

    task_list: list[dict[str, Any]] | None = None
    task_details: list[dict[str, Any]] | None = None
    plan_end: str | None = None
    plan_start: str | None = None


async def complete_revision_after_agi(plan_id: str, webhook_secret: str | None, body: RevisionCompleteBody | None) -> dict[str, Any]:
    """Called from internal webhook when AGI completes a revision (not enterprise-facing)."""
    from app.core.config import settings

    _require_db()
    expected = settings.DECOMPOSITION_REVISION_WEBHOOK_SECRET
    if not expected or not webhook_secret or webhook_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing webhook secret.")

    doc = await plan_repository.find_by_plan_id(plan_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if doc.get("status") != "REVISION_IN_PROGRESS":
        raise HTTPException(status_code=400, detail="Plan is not awaiting revision completion.")

    body = body or RevisionCompleteBody()
    task_list = body.task_list if body.task_list is not None else list(doc.get("task_list") or default_task_list())
    task_details = body.task_details if body.task_details is not None else list(doc.get("task_details") or default_task_details())
    plan_start = body.plan_start or doc.get("plan_start")
    plan_end = body.plan_end or doc.get("plan_end")
    if task_list:
        plan_start = plan_start or min(t.get("start_date", "") for t in task_list if isinstance(t, dict))
        plan_end = plan_end or max(t.get("end_date", "") for t in task_list if isinstance(t, dict))

    snaps = list(doc.get("revision_snapshots") or [])
    notes = doc.get("last_revision_notes") or "AGI revision"
    snaps.append({"revision_index": len(snaps), "notes": notes, "tasks": task_list})

    content = dict(doc.get("plan_content") or {})
    content["plan_version"] = int(content.get("plan_version") or 1) + 1
    content["generated_at"] = _utc_iso()

    await plan_repository.update_by_plan_id(
        plan_id,
        {
            "$set": {
                "status": "PLAN_REVIEW_REQUIRED",
                "task_list": task_list,
                "task_details": task_details,
                "plan_start": plan_start,
                "plan_end": plan_end,
                "plan_content": content,
                "revision_snapshots": snaps,
                "revision_requested_at": None,
            }
        },
    )
    return {"message": "Revision applied; plan is ready for enterprise review again.", "plan_id": plan_id, "status": "PLAN_REVIEW_REQUIRED"}


# --- Removed legacy demo paths (increase_revision, request_plan_revision_status) — use request_plan_revision ---


async def apply_flagged_tasks_for_revision_notes(plan_id: str, enterprise_profile_id: str) -> list[dict[str, Any]]:
    """Return flagged task id/name tuples for modal pre-fill."""
    doc = await _get_owned_plan(plan_id, enterprise_profile_id)
    _assert_kicked_off(doc)
    flagged = list(doc.get("flagged_task_ids") or [])
    details = {int(d.get("id")): d for d in (doc.get("task_details") or []) if d.get("id") is not None}
    out: list[dict[str, Any]] = []
    for tid in flagged:
        try:
            i = int(tid)
        except (TypeError, ValueError):
            continue
        row = details.get(i) or {}
        out.append({"id": i, "name": row.get("task_name") or row.get("task_id") or str(i)})
    return out

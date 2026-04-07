from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

from app.models.decomposition import PlanStatus
from app.schemas.decomposition.plans import (
    ChecklistStatusResponse,
    ConfirmPlanRequest,
    LockPlanRequest,
    PlanStateResponse,
    RevisionCounterResponse,
    RevisionRequest,
    SummaryResponse,
)

_PLANS_DB = {
    1: {
        "revision": 0,
        "status": "PLAN_REVIEW_REQUIRED",
        "checklist": {"item1": True, "item2": True, "item3": False},
    }
}

_CONFIRM_PLAN_STATUS_DB = {1: "PLAN REVIEW REQUIRED"}
_CONFIRM_CHECKLIST_DB = {1: {"item1": True, "item2": True, "item3": True}}

_LOCK_PLAN_STATUS_DB = {1: "CONFIRMED"}
_PROJECT_STARTED_DB = {1: True}


def list_plans() -> list[dict]:
    return []


def get_plan(plan_id: str):
    raise HTTPException(
        status_code=404,
        detail={
            "error": "Plan not found",
            "plan_id": plan_id,
            "message": f"No plan with ID '{plan_id}' exists.",
        },
    )


def get_plan_status(plan_id: str):
    raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")


def confirm_plan(plan_id: str, body: ConfirmPlanRequest) -> dict:
    return {
        "message": "Plan confirmed successfully.",
        "plan_id": plan_id,
        "new_status": PlanStatus.PLAN_CONFIRMED,
        "next_step": "Contributor matching is now running. Teams module will begin populating.",
    }


def request_plan_revision(plan_id: str, body: RevisionRequest) -> dict:
    return {
        "message": "Revision request submitted.",
        "plan_id": plan_id,
        "new_status": PlanStatus.REVISION_IN_PROGRESS,
        "estimated_revision": "15-60 min",
        "next_step": "Plan is read-only. Enterprise will be notified when revision is complete.",
    }


def lock_plan(plan_id: str, body: LockPlanRequest) -> dict:
    return {
        "message": "Plan is now locked. Delivery has started.",
        "plan_id": plan_id,
        "new_status": PlanStatus.PLAN_LOCKED,
        "locked_by": body.contributor_id,
        "next_step": "Changes require a formal Change Request via Admin.",
    }


def kickoff(plan_id: str) -> dict:
    return {"message": "Plan generated successfully", "status": "PLAN_REVIEW_REQUIRED"}


def withdraw_plan(plan_id: str) -> dict:
    return {"message": f"Plan {plan_id} withdrawn successfully", "status": "WITHDRAWN"}


def get_revision(plan_id: int) -> RevisionCounterResponse:
    if plan_id not in _PLANS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")
    return RevisionCounterResponse(plan_id=plan_id, revision=_PLANS_DB[plan_id]["revision"])


def increase_revision(plan_id: int) -> dict:
    if plan_id not in _PLANS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")
    if _PLANS_DB[plan_id]["revision"] >= 3:
        return {"message": "Max revision reached"}
    _PLANS_DB[plan_id]["revision"] += 1
    return {"revision": _PLANS_DB[plan_id]["revision"]}


def get_summary(plan_id: int) -> SummaryResponse:
    return SummaryResponse(total_milestones=5, total_tasks=20, effort_days=15)


def request_plan_revision_status(plan_id: int) -> dict:
    if plan_id not in _PLANS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")
    if _PLANS_DB[plan_id]["status"] != "PLAN_REVIEW_REQUIRED":
        raise HTTPException(status_code=400, detail="Not allowed")
    return {"message": "Revision requested"}


def get_status(plan_id: int) -> PlanStateResponse:
    if plan_id not in _PLANS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")
    return PlanStateResponse(status=_PLANS_DB[plan_id]["status"])


def get_checklist_status(plan_id: int) -> ChecklistStatusResponse:
    if plan_id not in _PLANS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")
    return ChecklistStatusResponse(**deepcopy(_PLANS_DB[plan_id]["checklist"]))


def confirm_plan_status(plan_id: int) -> dict:
    if plan_id not in _PLANS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")

    checklist = _PLANS_DB[plan_id]["checklist"]
    if not all(checklist.values()):
        raise HTTPException(status_code=400, detail="Checklist incomplete")

    _PLANS_DB[plan_id]["status"] = "PLAN_CONFIRMED"
    return {"message": "Plan confirmed"}


def confirm_plan_action(plan_id: int) -> dict:
    if plan_id not in _CONFIRM_PLAN_STATUS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")

    status = _CONFIRM_PLAN_STATUS_DB[plan_id]
    if status == "CONFIRMED":
        raise HTTPException(status_code=400, detail="Plan already confirmed")
    if status == "REVISION IN PROGRESS":
        raise HTTPException(status_code=400, detail="Cannot confirm while revision is in progress")

    checklist = _CONFIRM_CHECKLIST_DB.get(plan_id)
    if not checklist or not all(checklist.values()):
        raise HTTPException(status_code=400, detail="Checklist not completed")

    _CONFIRM_PLAN_STATUS_DB[plan_id] = "CONFIRMED"
    return {"message": "Plan confirmed successfully", "status": _CONFIRM_PLAN_STATUS_DB[plan_id]}


def lock_plan_action(plan_id: int) -> dict:
    if plan_id not in _LOCK_PLAN_STATUS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _PROJECT_STARTED_DB.get(plan_id, False):
        raise HTTPException(status_code=403, detail="This project has not been kicked off yet")

    status = _LOCK_PLAN_STATUS_DB[plan_id]
    if status != "CONFIRMED":
        raise HTTPException(status_code=400, detail="Plan must be CONFIRMED before locking")
    if status == "PLAN LOCKED":
        raise HTTPException(status_code=400, detail="Plan is already locked")

    _LOCK_PLAN_STATUS_DB[plan_id] = "PLAN LOCKED"
    return {
        "message": "Plan locked successfully. Delivery has started.",
        "status": _LOCK_PLAN_STATUS_DB[plan_id],
    }


def get_lock_status(plan_id: int) -> dict:
    if plan_id not in _LOCK_PLAN_STATUS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _PROJECT_STARTED_DB.get(plan_id, False):
        raise HTTPException(status_code=403, detail="This project has not been kicked off yet")

    status = _LOCK_PLAN_STATUS_DB[plan_id]
    return {
        "plan_id": plan_id,
        "status": status,
        "is_locked": status == "PLAN LOCKED",
        "can_request_revision": status not in ["PLAN LOCKED"],
        "can_confirm": status == "PLAN REVIEW REQUIRED",
    }

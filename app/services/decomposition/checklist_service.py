"""Review checklist and SOW vs plan date checks (Planning §8.1.2, DCP-006)."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

from fastapi import HTTPException

from app.core.database import is_db_connected
from app.schemas.decomposition.checklist import ChecklistUpdate
from app.services.decomposition import plan_repository

_DCP005 = "This project has not been kicked off yet."


async def _load_doc(enterprise_profile_id: str, plan_id: str) -> dict:
    if not is_db_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    doc = await plan_repository.find_by_plan_id(plan_id)
    if doc is None or doc.get("enterprise_profile_id") != enterprise_profile_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not doc.get("kicked_off") or doc.get("status") == "PENDING_KICKOFF":
        raise HTTPException(status_code=403, detail=_DCP005)
    return doc


def _checklist_editable(doc: dict) -> None:
    if doc.get("status") != "PLAN_REVIEW_REQUIRED":
        raise HTTPException(
            status_code=400,
            detail="Checklist can only be edited while the plan awaits review (PLAN_REVIEW_REQUIRED).",
        )


async def get_checklist(enterprise_profile_id: str, plan_id: str) -> dict:
    doc = await _load_doc(enterprise_profile_id, plan_id)
    return deepcopy(doc.get("checklist") or {"item1": False, "item2": False, "item3": False})


async def update_checklist(enterprise_profile_id: str, plan_id: str, data: ChecklistUpdate) -> dict:
    doc = await _load_doc(enterprise_profile_id, plan_id)
    _checklist_editable(doc)
    await plan_repository.update_by_plan_id(plan_id, {"$set": {"checklist": data.model_dump()}})
    return {"message": "Checklist updated"}


async def validate_checklist(enterprise_profile_id: str, plan_id: str) -> dict:
    doc = await _load_doc(enterprise_profile_id, plan_id)
    checklist = doc.get("checklist") or {}
    all_checked = bool(checklist.get("item1") and checklist.get("item2") and checklist.get("item3"))
    return {"all_checked": all_checked, "can_confirm": all_checked and doc.get("status") == "PLAN_REVIEW_REQUIRED"}


async def validate_dates(enterprise_profile_id: str, plan_id: str) -> dict:
    doc = await _load_doc(enterprise_profile_id, plan_id)
    try:
        sow_start = date.fromisoformat(str(doc.get("sow_start", ""))[:10])
        sow_end = date.fromisoformat(str(doc.get("sow_end", ""))[:10])
        plan_start = date.fromisoformat(str(doc.get("plan_start", ""))[:10])
        plan_end = date.fromisoformat(str(doc.get("plan_end", ""))[:10])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date fields on plan") from exc

    diff = (plan_end - sow_end).days
    warning = f"Plan end date exceeds SOW committed end date by {diff} days." if diff > 0 else None
    return {
        "sow_start": sow_start,
        "sow_end": sow_end,
        "plan_start": plan_start,
        "plan_end": plan_end,
        "warning": warning,
    }


REVIEW_LABELS: dict[str, str] = {
    "item1": "I have reviewed all milestones, tasks, and their acceptance criteria.",
    "item2": "I confirm the project timeline fits within the SOW dates.",
    "item3": "I confirm the required skills and seniority levels match the project needs.",
}


async def get_review_checklist(enterprise_profile_id: str, plan_id: str) -> dict:
    doc = await _load_doc(enterprise_profile_id, plan_id)
    c = doc.get("checklist") or {"item1": False, "item2": False, "item3": False}
    items = [
        {"item_id": "item1", "label": REVIEW_LABELS["item1"], "is_checked": bool(c.get("item1"))},
        {"item_id": "item2", "label": REVIEW_LABELS["item2"], "is_checked": bool(c.get("item2"))},
        {"item_id": "item3", "label": REVIEW_LABELS["item3"], "is_checked": bool(c.get("item3"))},
    ]
    all_done = all(i["is_checked"] for i in items)
    return {
        "plan_id": plan_id,
        "checklist": items,
        "checklist_complete": all_done,
        "sow_start": doc.get("sow_start"),
        "sow_end": doc.get("sow_end"),
        "plan_start": doc.get("plan_start"),
        "plan_end": doc.get("plan_end"),
        "date_warning": (await validate_dates(enterprise_profile_id, plan_id)).get("warning"),
    }


async def update_review_checklist_item(
    enterprise_profile_id: str,
    plan_id: str,
    *,
    item_id: str,
    is_checked: bool,
    updated_by: str,
) -> dict:
    _ = updated_by
    if item_id not in ("item1", "item2", "item3"):
        raise HTTPException(status_code=400, detail="Invalid checklist item_id")
    doc = await _load_doc(enterprise_profile_id, plan_id)
    _checklist_editable(doc)
    c = dict(doc.get("checklist") or {"item1": False, "item2": False, "item3": False})
    c[item_id] = is_checked
    await plan_repository.update_by_plan_id(plan_id, {"$set": {"checklist": c}})
    all_done = bool(c.get("item1") and c.get("item2") and c.get("item3"))
    return {
        "plan_id": plan_id,
        "item_id": item_id,
        "is_checked": is_checked,
        "checklist_complete": all_done,
        "can_confirm_plan": all_done,
    }

from __future__ import annotations

from copy import deepcopy
from datetime import date

from fastapi import HTTPException

from app.schemas.decomposition.checklist import ChecklistUpdate

_CHECKLIST_DB = {1: {"item1": False, "item2": False, "item3": False}}
_PLAN_DATES = {
    1: {
        "sow_start": date(2026, 4, 1),
        "sow_end": date(2026, 4, 10),
        "plan_start": date(2026, 4, 1),
        "plan_end": date(2026, 4, 12),
    }
}


def get_checklist(plan_id: int) -> dict:
    return deepcopy(_CHECKLIST_DB.get(plan_id, {}))


def update_checklist(plan_id: int, data: ChecklistUpdate) -> dict:
    _CHECKLIST_DB[plan_id] = data.model_dump()
    return {"message": "Checklist updated"}


def validate_checklist(plan_id: int) -> dict:
    checklist = _CHECKLIST_DB.get(plan_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")

    all_checked = all(checklist.values())
    return {"all_checked": all_checked, "can_confirm": all_checked}


def validate_dates(plan_id: int) -> dict:
    dates = _PLAN_DATES.get(plan_id)
    if not dates:
        raise HTTPException(status_code=404, detail="Plan not found")

    diff = (dates["plan_end"] - dates["sow_end"]).days
    warning = f"Plan exceeds SOW by {diff} days" if diff > 0 else None

    return {
        "sow_start": dates["sow_start"],
        "sow_end": dates["sow_end"],
        "plan_start": dates["plan_start"],
        "plan_end": dates["plan_end"],
        "warning": warning,
    }


def get_review_checklist(plan_id: str) -> dict:
    raise HTTPException(status_code=404, detail=f"Checklist for plan '{plan_id}' not found.")


def update_review_checklist_item(plan_id: str, item_id: str, is_checked: bool, updated_by: str):
    raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

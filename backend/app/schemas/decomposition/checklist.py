from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.models.decomposition import ChecklistUpdateRequest, ChecklistUpdateResponse, ReviewChecklistItem


class ChecklistUpdate(BaseModel):
    item1: bool
    item2: bool
    item3: bool


class ChecklistStateResponse(BaseModel):
    item1: bool
    item2: bool
    item3: bool


class ChecklistValidationResponse(BaseModel):
    all_checked: bool
    can_confirm: bool


class ChecklistDateValidationResponse(BaseModel):
    sow_start: date
    sow_end: date
    plan_start: date
    plan_end: date
    warning: str | None = None


class ReviewChecklistResponse(BaseModel):
    plan_id: str
    checklist: list[ReviewChecklistItem]
    checklist_complete: bool

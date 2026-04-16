from __future__ import annotations

from pydantic import BaseModel

from app.models.decomposition import (
    ConfirmPlanRequest,
    LockPlanRequest,
    PlanResponse,
    PlanStatus,
    PlanStatusResponse,
    RevisionRequest,
)


class PlanActionResponse(BaseModel):
    message: str
    status: str


class WithdrawPlanResponse(BaseModel):
    message: str
    status: str


class RevisionCounterResponse(BaseModel):
    plan_id: str
    revision: int


class SummaryResponse(BaseModel):
    total_milestones: int
    total_tasks: int
    effort_days: int


class ChecklistStatusResponse(BaseModel):
    item1: bool
    item2: bool
    item3: bool


class PlanStateResponse(BaseModel):
    status: str


class PlanMessageResponse(BaseModel):
    message: str

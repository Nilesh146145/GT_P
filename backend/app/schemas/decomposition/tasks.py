from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TaskListResponse(BaseModel):
    tasks: list[dict[str, Any]]


class MilestoneMapResponse(BaseModel):
    milestones: dict[str, list[dict[str, Any]]]


class CriticalTasksResponse(BaseModel):
    critical_tasks: list[dict[str, Any]]


class FlagTaskResponse(BaseModel):
    message: str
    total_flagged: int
    flagged_tasks: list[int]

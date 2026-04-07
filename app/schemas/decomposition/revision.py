from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.decomposition import PlanReviewPageResponse, RevisionRound


class RevisionNotesRequest(BaseModel):
    notes: str = Field(..., min_length=30, max_length=2000)


class RevisionModalResponse(BaseModel):
    revision_count: int
    max_revisions: int
    status: str
    flagged_tasks: list[dict[str, Any]]


class RevisionSubmissionResponse(BaseModel):
    message: str
    revision_count: int
    status: str


class RevisedPlanResponse(BaseModel):
    current_revision: int
    tasks: list[dict[str, Any]]
    changes: dict[str, list[int]]
    summary: dict[str, int]


class RevisionDetailResponse(BaseModel):
    revision_id: int
    notes: str
    tasks: list[dict[str, Any]]

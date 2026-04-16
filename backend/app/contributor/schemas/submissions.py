from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SubmissionStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    needs_revision = "needs_revision"
    accepted = "accepted"
    rejected = "rejected"


class SubmissionMode(str, Enum):
    draft = "draft"
    submit = "submit"
    resubmit = "resubmit"

class ChecklistAcknowledgement(BaseModel):
    """Maps to acceptance criteria; persisted on draft/latest submission via PATCH."""

    criterion_id: str
    acknowledged: bool = False
    notes: str | None = Field(None, max_length=200)


class EvidenceItemInput(BaseModel):
    label: str
    description: str | None = None
    file_id: str | None = None
    url: str | None = None
    checklist_item_id: str | None = None


class SubmissionFileRef(BaseModel):
    id: str
    filename: str | None = None
    mime_type: str | None = None


class EvidenceItemOut(BaseModel):
    label: str
    description: str | None = None
    file_id: str | None = None
    url: str | None = None
    checklist_item_id: str | None = None


class RubricScore(BaseModel):
    criterion_id: str
    score: float | None = None
    max_score: float | None = None
    comment: str | None = None


class CreateSubmissionBody(BaseModel):
    submission_mode: SubmissionMode
    version: int | None = None
    notes: str | None = None
    file_ids: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItemInput] = Field(default_factory=list)
    structured_responses: list[dict[str, Any]] = Field(default_factory=list)


class PatchSubmissionBody(BaseModel):
    """Same optional fields as save-draft update."""

    version: int | None = None
    notes: str | None = None
    file_ids: list[str] | None = None
    evidence_items: list[EvidenceItemInput] | None = None
    structured_responses: list[dict[str, Any]] | None = None
    checklist_acknowledgements: list[ChecklistAcknowledgement] | None = None


class SubmitBody(BaseModel):
    notes: str | None = None
    confirm_checklist_complete: bool = False


class ResubmitBody(BaseModel):
    notes: str | None = None
    file_ids: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItemInput] = Field(default_factory=list)


class SubmissionDetail(BaseModel):
    id: str
    task_id: str
    version: int
    submitted_at: datetime | None
    status: SubmissionStatus
    notes: str | None
    files: list[SubmissionFileRef]
    evidence: list[EvidenceItemOut]
    checklist_acknowledgements: list[ChecklistAcknowledgement] = Field(
        default_factory=list
    )
    review_score: float | None = None
    reviewer_feedback: str | None = None
    rubric_scores: list[RubricScore] = Field(default_factory=list)
    structured_responses: list[dict[str, Any]] = Field(default_factory=list)


class SubmissionListItem(BaseModel):
    id: str
    task_id: str
    version: int
    submitted_at: datetime | None
    status: SubmissionStatus


class PaginatedSubmissions(BaseModel):
    items: list[SubmissionListItem]
    page: int
    page_size: int
    total: int


class ReviewFeedbackResponse(BaseModel):
    task_id: str
    submission_id: str | None
    reviewer_feedback: str | None = None
    review_score: float | None = None
    rubric_scores: list[RubricScore] = Field(default_factory=list)

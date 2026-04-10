from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class ReviewerProjectItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    status: str
    assigned_at: Optional[str] = Field(default=None, alias="assignedAt")
    task_kind: Optional[str] = Field(default=None, alias="taskKind")
    related_id: Optional[str] = Field(default=None, alias="relatedId")
    notes: Optional[str] = None


class CreateReviewerAssignmentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    task_kind: str = Field(
        default="other",
        validation_alias=AliasChoices("task_kind", "taskKind"),
    )
    related_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("related_id", "relatedId"),
    )
    notes: Optional[str] = Field(default=None, max_length=2000)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("task_kind")
    @classmethod
    def task_kind_allowed(cls, value: str) -> str:
        allowed = frozenset({"project", "evidence_review", "other"})
        normalized = (value or "other").strip().lower()
        if normalized not in allowed:
            raise ValueError(f'task_kind must be one of: {", ".join(sorted(allowed))}')
        return normalized


class UpdateReviewerAssignmentStatusRequest(BaseModel):
    status: Literal["pending", "in_progress", "completed"]


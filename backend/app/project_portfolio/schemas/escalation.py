from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class EscalationCreate(BaseModel):
    project_id: str
    reason: str | None = Field(
        default=None,
        description="Required unless rework_request_id is set (then defaults from rework).",
    )
    severity: str | None = None
    rework_request_id: str | None = Field(
        default=None,
        description="If set, converts that rework into a formal escalation for this project.",
    )

    @model_validator(mode="after")
    def _reason_or_rework(self) -> "EscalationCreate":
        if (self.reason is None or not str(self.reason).strip()) and not self.rework_request_id:
            raise ValueError("reason is required when rework_request_id is not provided")
        return self


class EscalationRecord(BaseModel):
    id: str
    project_id: str
    reason: str
    severity: str | None
    raised_at: datetime
    rework_request_id: str | None = None

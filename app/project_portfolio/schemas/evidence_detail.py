from datetime import datetime

from pydantic import BaseModel, Field

from app.project_portfolio.schemas.evidence import EvidencePackStatus


class EvidenceArtifact(BaseModel):
    name: str
    content_type: str | None = None
    url: str | None = None


class EvidencePackDetail(BaseModel):
    """Full evidence pack for View Evidence Pack."""

    id: str
    project_id: str
    title: str
    status: EvidencePackStatus
    milestone_id: str
    milestone_key: str
    milestone_name: str | None = None
    submitted_at: datetime
    summary: str | None = None
    reviewer_notes: str | None = None
    artifacts: list[EvidenceArtifact] = Field(default_factory=list)


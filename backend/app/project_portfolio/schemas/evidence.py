from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class EvidencePackStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DRAFT = "DRAFT"


class EvidencePackItem(BaseModel):
    id: str
    title: str
    status: EvidencePackStatus
    milestone_id: str = Field(description="Canonical milestone id, e.g. ms_proj_001_m2")
    milestone_key: str = Field(description="Short label for filters, e.g. M1, M2")
    submitted_at: datetime


class EvidencePackGroup(BaseModel):
    """Evidence packs under one milestone (TAB-3 grouping)."""

    milestone_id: str
    milestone_key: str
    milestone_name: str | None = None
    evidence_packs: list[EvidencePackItem]


class EvidencePacksResponse(BaseModel):
    project_id: str
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    total: int = Field(description="Total packs matching filters (before pagination slice)")
    start_date: date | None = None
    end_date: date | None = None
    status_filter: EvidencePackStatus | None = None
    milestone_filter: str | None = None
    groups: list[EvidencePackGroup]


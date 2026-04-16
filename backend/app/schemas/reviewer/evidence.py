from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EvidenceRecommendationType(str, Enum):
    ACCEPT = "ACCEPT"
    REWORK = "REWORK"


class EvidenceRecommendRequest(BaseModel):
    score: int = Field(..., ge=0, le=100)
    comment: str = Field(..., min_length=1, max_length=4000)
    recommendation: EvidenceRecommendationType


class EvidenceRecommendResult(BaseModel):
    evidence_id: str = Field(alias="evidenceId")
    score: int
    recommendation: str

    model_config = ConfigDict(populate_by_name=True)


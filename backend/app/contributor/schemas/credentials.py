from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DateFilter(str, Enum):
    D30 = "30d"
    D90 = "90d"
    M6 = "6m"


class AcademicMapping(BaseModel):
    """Structured academic credit / course mapping; extend fields as your domain requires."""

    model_config = {"extra": "allow"}

    label: str | None = None
    credits: float | None = None
    course_code: str | None = None


class CredentialListItem(BaseModel):
    id: str
    title: str
    skill: str
    level: str
    issued_at: datetime
    task_id: str
    task_title: str
    project_title: str
    podl_hash: str
    verification_url: str
    review_score: float | None = None
    hours_validated: float | None = None
    academic_mapping: AcademicMapping | dict[str, Any] | None = None
    skill_tags: list[str] | None = None
    designation: str | None = None
    seniority: str | None = None
    acceptance_date: datetime | None = None
    quality_indicator: str | None = None
    platform_verified: bool = True


class CredentialDetail(BaseModel):
    title: str
    skill: str
    level: str
    issued_at: datetime
    task_id: str
    task_title: str
    project_title: str
    podl_hash: str
    verification_url: str
    review_score: float | None = None
    hours_validated: float | None = None
    certificate_file_url: str | None = None
    academic_mapping: AcademicMapping | dict[str, Any] | None = None
    revoked: bool = False
    skill_tags: list[str] | None = None
    designation: str | None = None
    seniority: str | None = None
    acceptance_date: datetime | None = None
    quality_indicator: str | None = None
    platform_verified: bool = True


class CredentialShareRequest(BaseModel):
    target_type: str = Field(..., description="e.g. university")
    target_id: str | None = None
    consent: bool
    share_fields: list[str] | None = Field(
        default=None,
        description="Optional: skills, hours, review_score, credential",
    )


class AcademicPortfolioRequest(BaseModel):
    format: str = Field(default="pdf", description="Export format, default pdf")
    include_tasks: bool = False
    include_credentials: bool = False
    include_hours: bool = False
    include_feedback: bool = False


class CredentialListResponse(BaseModel):
    items: list[CredentialListItem]
    page: int
    page_size: int
    total: int


class ShareResponse(BaseModel):
    credential_id: str
    share_id: str
    status: str
    target_type: str
    target_id: str | None = None
    public_url: str | None = None


class AcademicPortfolioResponse(BaseModel):
    credential_id: str
    format: str
    download_url: str | None = None
    job_id: str | None = Field(default=None, description="If generation is async")


class WalletSummaryResponse(BaseModel):
    total_credentials: int
    skills_verified: int
    tasks_accepted: int
    acceptance_rate: float


class CredentialWalletCard(BaseModel):
    credential_id: str
    credential_title: str
    task_type: str
    skill_tags: list[str]
    designation: str
    seniority: str
    acceptance_date: datetime
    quality_indicator: str | None = None
    platform_verified: bool = True
    certificate_pdf_url: str | None = None
    shareable_link: str | None = None


class CredentialWalletCardsResponse(BaseModel):
    items: list[CredentialWalletCard]
    page: int
    page_size: int
    total: int


class PublicCredentialView(BaseModel):
    """Public share view: portfolio-safe fields only (no PII, hashes, or certificate URLs)."""

    task_type: str
    skills_evidenced: list[str]
    designation: str
    seniority: str
    quality_indicator: str | None = None
    platform_verified: bool = True


class SkillVerificationItem(BaseModel):
    skill_tag: str
    status: str
    credential_count: int = 0
    evidence_source: str
    seniority_level: str | None = None


class SkillVerificationResponse(BaseModel):
    items: list[SkillVerificationItem]

"""Pydantic request/response bodies for Manual SOW API."""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.manual_sow.enums import CommercialSectionKey, ExtractionReviewState


# ── Review & gaps ────────────────────────────────────────────────────────────


class ExtractionReviewPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    review_state: str = Field(alias="review_state")
    edited_text: Optional[str] = Field(default=None, alias="edited_text")

    @field_validator("review_state")
    @classmethod
    def allowed(cls, v: str) -> str:
        allowed = {e.value for e in ExtractionReviewState}
        if v not in allowed:
            raise ValueError(f"review_state must be one of {allowed}")
        return v


class GapItemPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    is_resolved: Optional[bool] = Field(default=None, alias="is_resolved")
    is_acknowledged: Optional[bool] = Field(default=None, alias="is_acknowledged")
    is_dismissed: Optional[bool] = Field(default=None, alias="is_dismissed")
    remediation_suggestions: Optional[list[str]] = Field(default=None, alias="remediation_suggestions")


class ApprovalAuthoritiesPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sow_submitter: Optional[str] = Field(default=None, alias="sow_submitter")
    business_owner_approver: str = Field(alias="business_owner_approver")
    final_approver: str = Field(alias="final_approver")
    legal_reviewer: Optional[str] = Field(default=None, alias="legal_reviewer")
    security_reviewer: Optional[str] = Field(default=None, alias="security_reviewer")


class GenerateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    include_extracted_sections: bool = Field(default=True, alias="include_extracted_sections")


class ConfirmSubmitBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    confirms_accuracy: bool = Field(alias="confirms_accuracy")
    notes: Optional[str] = None


class ApproveStageBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reviewer: str
    comments: Optional[str] = None
    checklist: Optional[dict[str, bool]] = None


class RejectStageBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reviewer: str
    reason: str
    specific_feedback: Optional[str] = Field(default=None, alias="specific_feedback")


class MarkSectionCompleteBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    section: CommercialSectionKey


class SowMetadataPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: Optional[str] = None
    tags: Optional[list[str]] = None
    stakeholders: Optional[list[str]] = None
    estimated_budget: Optional[float] = Field(default=None, alias="estimated_budget")


class AiGeneratedTextContent(BaseModel):
    """JSON inside `AI-generated-text`: narrative plus explicit tech list under `AI-generated-tech-stack`."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., min_length=1, max_length=240, description="Heading for the AI block.")
    tags: list[str] = Field(default_factory=list, description="Short technology / capability tags.")
    tech_stack: list[str] = Field(
        ...,
        min_length=1,
        max_length=40,
        alias="AI-generated-tech-stack",
        description='Concrete technologies as JSON array, e.g. ["Python","FastAPI","React","PostgreSQL"].',
    )
    summary: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Technology stack narrative suitable for Tech & Integrations.",
    )
    technology_stack_line: Optional[str] = Field(
        default=None,
        max_length=800,
        alias="technologyStackLine",
        description='Single-line stack for UI, e.g. "React (frontend) · Node.js (API layer) · PostgreSQL (primary database)".',
    )
    scalability_performance: Optional[str] = Field(
        default=None,
        max_length=2000,
        alias="scalabilityPerformance",
        description="Scalability, performance, and capacity notes for Section C (Technical Architecture).",
    )
    user_management_scope: Optional[str] = Field(
        default=None,
        max_length=2000,
        alias="userManagementScope",
        description="User management, roles, and IdP / SSO scope for Section C.",
    )
    sso_required: Optional[bool] = Field(
        default=None,
        alias="ssoRequired",
        description="Whether SSO is required for this project (Section C checkbox).",
    )

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        s = str(v).strip()
        return [s] if s else []

    @field_validator("tech_stack", mode="before")
    @classmethod
    def _coerce_tech_stack(cls, v: Any) -> list[str]:
        if v is None:
            raise ValueError("AI-generated-tech-stack is required (non-empty array of strings).")
        if isinstance(v, list):
            out = [str(x).strip() for x in v if str(x).strip()]
            if not out:
                raise ValueError("AI-generated-tech-stack must contain at least one technology name.")
            return out[:40]
        if isinstance(v, str):
            parts = [p.strip() for p in re.split(r"[,;|]", v) if p.strip()]
            if not parts:
                raise ValueError("AI-generated-tech-stack must contain at least one technology name.")
            return parts[:40]
        s = str(v).strip()
        if not s:
            raise ValueError("AI-generated-tech-stack must contain at least one technology name.")
        return [s]

    @model_validator(mode="after")
    def _ensure_derived_section_c_fields(self):
        updates: dict[str, Any] = {}
        line = (self.technology_stack_line or "").strip()
        if not line and self.tech_stack:
            line = " · ".join(f"{x} (stack component)" for x in self.tech_stack[:10])
        if line:
            updates["technology_stack_line"] = line
        if not (self.scalability_performance or "").strip():
            updates["scalability_performance"] = (
                "Define target concurrent users and p95 latency SLOs for APIs where applicable. "
                "Plan horizontal autoscaling for stateless tiers, caching for hot reads, and CDN for static assets when a web or hybrid client exists. "
                "Document load-test milestones before go-live."
            )
        if not (self.user_management_scope or "").strip():
            updates["user_management_scope"] = (
                "Application roles with least-privilege access; corporate directory integration when SSO is enabled."
            )
        if self.sso_required is None:
            updates["sso_required"] = True
        if not updates:
            return self
        return self.model_copy(update=updates)


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=100)
    sort: str = Field(default="created_at")
    order: str = Field(default="desc")

    @field_validator("sort")
    @classmethod
    def sort_field(cls, v: str) -> str:
        if v not in ("created_at", "updated_at", "title"):
            raise ValueError("sort must be created_at | updated_at | title")
        return v

    @field_validator("order")
    @classmethod
    def order_dir(cls, v: str) -> str:
        if v not in ("asc", "desc"):
            raise ValueError("order must be asc | desc")
        return v

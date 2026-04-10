"""Pydantic request/response bodies for Manual SOW API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

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

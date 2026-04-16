from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime
from app.schemas.common import WizardStatus, SOWStatus


# ══════════════════════════════════════════════
# STEP 9 — Review & Generate
# ══════════════════════════════════════════════

class Step9Input(BaseModel):
    business_owner_approver_id: str = Field(
        ..., description="User ID of Business Owner Approver — receives Stage 1 notification"
    )
    final_approver_id: str = Field(
        ..., description="User ID of Final Approver — receives Stage 5 sign-off notification"
    )
    legal_compliance_reviewer_id: Optional[str] = Field(
        None, description="Optional here — can be designated later in SOW Detail"
    )
    security_reviewer_id: Optional[str] = Field(
        None, description="Optional here — same as above"
    )


# ══════════════════════════════════════════════
# WIZARD DOCUMENT (stored in MongoDB)
# ══════════════════════════════════════════════

class WizardDocument(BaseModel):
    """Full wizard state stored as a MongoDB document."""
    id: Optional[str] = None
    enterprise_id: str
    created_by_user_id: str
    status: WizardStatus = WizardStatus.draft
    current_step: int = 0
    steps_completed: List[int] = []
    steps_skipped: List[int] = []

    # Step data — each step saved independently
    step_0: Optional[Any] = None
    step_1: Optional[Any] = None
    step_2: Optional[Any] = None
    step_3: Optional[Any] = None
    step_4: Optional[Any] = None
    step_5: Optional[Any] = None
    step_6: Optional[Any] = None
    step_7: Optional[Any] = None
    step_8: Optional[Any] = None
    step_9: Optional[Any] = None

    # Scoring
    confidence_score: float = 0.0
    confidence_breakdown: Optional[Any] = None

    # Meta
    last_saved: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ══════════════════════════════════════════════
# SOW DOCUMENT
# ══════════════════════════════════════════════

class HallucinationLayerResult(BaseModel):
    layer_id: int
    name: str
    active: bool = False
    status: str = "grey"  # grey | green | amber | red
    detail: Optional[str] = None


class QualityMetrics(BaseModel):
    overall_confidence: float = 0.0
    risk_score: float = 0.0
    risk_level: str = "Low"
    hallucination_flags: int = 0
    completeness_pct: float = 0.0
    completeness_status: str = "Incomplete"


class SOWDocument(BaseModel):
    id: Optional[str] = None
    wizard_id: str
    enterprise_id: str
    created_by_user_id: str
    status: SOWStatus = SOWStatus.draft

    # Approver designations
    business_owner_approver_id: str
    final_approver_id: str
    legal_compliance_reviewer_id: Optional[str] = None
    security_reviewer_id: Optional[str] = None

    # Generated content
    generated_content: Optional[str] = Field(
        None, description="Full generated SOW text (Markdown or HTML)"
    )
    generated_sections: Optional[Any] = Field(
        None, description="Section-by-section structured content with per-section confidence"
    )

    # Quality
    quality_metrics: Optional[QualityMetrics] = None
    hallucination_layers: Optional[List[HallucinationLayerResult]] = None

    # Prohibited clauses
    prohibited_clause_flags: Optional[List[str]] = None
    has_unresolved_prohibited_clauses: bool = False

    # Tracking
    submitted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ══════════════════════════════════════════════
# REQUEST/RESPONSE SCHEMAS
# ══════════════════════════════════════════════

class WizardCreateRequest(BaseModel):
    enterprise_id: str


class WizardCreateResponse(BaseModel):
    wizard_id: str
    message: str = "Wizard created. Auto-saves every 30 seconds."


class StepSaveResponse(BaseModel):
    wizard_id: str
    step: int
    confidence_score: float
    confidence_breakdown: Any
    hallucination_layers_active: int
    steps_completed: List[int]
    steps_skipped: List[int]
    validation_errors: List[str] = []
    warnings: List[str] = []


class SkipStepRequest(BaseModel):
    step: int


class SkipStepResponse(BaseModel):
    wizard_id: str
    step: int
    skipped: bool = True
    confidence_penalty: float
    new_confidence_score: float
    message: str


class GenerateSOWRequest(BaseModel):
    wizard_id: str


class GenerateSOWResponse(BaseModel):
    sow_id: str
    wizard_id: str
    status: str = "generating"
    message: str = "SOW generation started. This takes 30–120 seconds."
    quality_metrics: Optional[QualityMetrics] = None


class SOWActionRequest(BaseModel):
    action: str = Field(..., description="submit | request_changes | reject_regenerate")
    change_notes: Optional[str] = Field(
        default=None,
        description="Required for request_changes (non-empty after trim). Optional for reject_regenerate.",
    )


# ══════════════════════════════════════════════
# AUTH SCHEMAS
# ══════════════════════════════════════════════

class UserRegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    full_name: str
    organisation: str
    role: str = "enterprise_user"


class UserLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    email: str

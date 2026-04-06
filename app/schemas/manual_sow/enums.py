"""Enumerations for Manual SOW intake API (spec §2)."""

from enum import Enum


class ManualSowStatus(str, Enum):
    draft = "draft"
    parsing = "parsing"
    review = "review"
    approval = "approval"
    approved = "approved"
    rejected = "rejected"
    changes_requested = "changes_requested"
    archived = "archived"


class SowIntakeMode(str, Enum):
    manual_upload = "manual_upload"
    ai_generated = "ai_generated"


class ConfidentialityLevel(str, Enum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    restricted = "restricted"


class DataSensitivityClass(str, Enum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    restricted = "restricted"


class UploadProcessingState(str, Enum):
    idle = "idle"
    validating = "validating"
    uploading = "uploading"
    extracting = "extracting"
    analyzing = "analyzing"
    detecting = "detecting"
    scoring = "scoring"
    complete = "complete"
    error = "error"


class ExtractionCategory(str, Enum):
    business_objectives = "business_objectives"
    user_context = "user_context"
    features = "features"
    timeline = "timeline"
    budget = "budget"
    compliance = "compliance"
    assumptions = "assumptions"
    technical = "technical"
    risk = "risk"


class ExtractionReviewState(str, Enum):
    pending = "pending"
    accepted = "accepted"
    edited = "edited"
    excluded = "excluded"


class ContextDetectionStatus(str, Enum):
    PRESENT = "PRESENT"
    PARTIAL = "PARTIAL"
    ABSENT = "ABSENT"


class GapSeverity(str, Enum):
    critical = "critical"
    important = "important"
    optional = "optional"


class CommercialSectionKey(str, Enum):
    businessContext = "businessContext"
    deliveryScope = "deliveryScope"
    techIntegrations = "techIntegrations"
    timelineTeam = "timelineTeam"
    budgetRisk = "budgetRisk"
    governance = "governance"
    commercialLegal = "commercialLegal"


class CommercialSectionStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    complete = "complete"
    pre_populated = "pre_populated"


class ApprovalStageKey(str, Enum):
    business = "business"
    glimmora_commercial = "glimmora_commercial"
    legal = "legal"
    security = "security"
    final = "final"


class ApprovalStageStatus(str, Enum):
    pending = "pending"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"


STAGE_ORDER: list[ApprovalStageKey] = [
    ApprovalStageKey.business,
    ApprovalStageKey.glimmora_commercial,
    ApprovalStageKey.legal,
    ApprovalStageKey.security,
    ApprovalStageKey.final,
]

STAGE_SLA_DAYS: dict[str, int] = {
    "business": 3,
    "glimmora_commercial": 2,
    "legal": 5,
    "security": 3,
    "final": 2,
}

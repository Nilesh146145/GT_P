from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum


# ──────────────────────────────────────────────
# STEP 0 — ENUMS
# ──────────────────────────────────────────────

class StrategicContext(str, Enum):
    new_market = "New market opportunity"
    regulatory = "Regulatory compliance obligation"
    competitive = "Competitive catch-up"
    internal_efficiency = "Internal efficiency improvement"
    cost_reduction = "Cost reduction"
    revenue_generation = "Revenue generation"
    cx_improvement = "Customer experience improvement"
    digital_transformation = "Digital transformation"
    other = "Other"


class AgeRange(str, Enum):
    under_18 = "Under 18"
    range_18_35 = "18–35"
    range_36_55 = "36–55"
    over_55 = "55+"
    mixed = "Mixed"


class TechLiteracy(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"


class PrimaryDevice(str, Enum):
    mobile = "Mobile"
    desktop = "Desktop"
    both = "Both"
    kiosk = "Kiosk/POS"


class LanguageOption(str, Enum):
    english = "English"
    hindi = "Hindi"
    tamil = "Tamil"
    telugu = "Telugu"
    bengali = "Bengali"
    arabic = "Arabic"
    french = "French"
    other = "Other"


class TranslationProvider(str, Enum):
    client = "Client provides translated strings"
    glimmora = "GlimmoraTeam arranges translation"
    third_party = "Third-party translation service — client pays"


# ──────────────────────────────────────────────
# STEP 0 — SUB-MODELS
# ──────────────────────────────────────────────

class BusinessObjective(BaseModel):
    objective: str = Field(..., min_length=1, max_length=200, description="Objective statement")
    measurable_target: str = Field(
        ..., min_length=1, max_length=100, description="Measurable target (WIZ-010)"
    )
    target_timeline: str = Field(..., max_length=50, description="Target timeline")


class PainPoint(BaseModel):
    problem_description: str = Field(..., max_length=300)
    who_experiences_it: str = Field(..., description="Persona or role name")


class EndUserProfile(BaseModel):
    role_name: str = Field(..., max_length=100)
    approximate_user_count: str = Field(..., description="Numeric or range e.g. '50,000+'")
    age_range: AgeRange
    tech_literacy: TechLiteracy
    primary_device: PrimaryDevice
    geography: str = Field(..., description="Single country or multiple countries")
    accessibility_needs: str = Field(..., description="Yes / No / Unknown")


class SuccessMetric(BaseModel):
    metric_name: str = Field(..., max_length=100)
    baseline_value: str = Field(..., description="Current state measurement")
    target_value: str
    measurement_method: str = Field(..., max_length=100)
    timeframe: str = Field(..., description="Timeframe to measure")


# ──────────────────────────────────────────────
# STEP 0 — SECTION SCHEMAS
# ──────────────────────────────────────────────

class Step0SectionA(BaseModel):
    """Section A — Project Vision & Business Context"""
    project_vision: str = Field(
        ..., min_length=50, max_length=500,
        description="In one or two sentences, describe what this project is and what it will achieve."
    )
    business_objectives: List[BusinessObjective] = Field(
        ..., min_length=1, max_length=6,
        description="SMART objectives — min 1, max 6"
    )
    pain_points: List[PainPoint] = Field(
        ..., min_length=1, max_length=8,
        description="Problems being solved — min 1, max 8"
    )
    strategic_context: Optional[StrategicContext] = None
    strategic_context_other: Optional[str] = Field(None, max_length=200)
    business_criticality: str = Field(
        ..., description="Mission-critical / Business-important / Standard / Low"
    )

    @field_validator("business_objectives")
    @classmethod
    def validate_objectives(cls, v):
        if not v:
            raise ValueError("At least one business objective is required.")
        return v


class Step0SectionB(BaseModel):
    """Section B — Current State & Desired Future State"""
    current_state_not_applicable: bool = Field(
        False, description="True if this is a completely new capability"
    )
    current_state_description: Optional[str] = Field(None, min_length=30, max_length=1000)
    desired_future_state: str = Field(
        ..., min_length=30, max_length=1000,
        description="What does success look like once this project is live?"
    )
    previous_attempts: Optional[str] = Field(None, max_length=500)

    @field_validator("current_state_description")
    @classmethod
    def validate_current_state(cls, v, info):
        data = info.data
        if not data.get("current_state_not_applicable") and not v:
            raise ValueError("Current state description is required unless this is a completely new capability.")
        return v


class Step0SectionC(BaseModel):
    """Section C — Target End Users"""
    end_user_profiles: List[EndUserProfile] = Field(
        ..., min_length=1, max_length=10
    )
    languages: Optional[List[LanguageOption]] = None
    translation_provider: Optional[TranslationProvider] = None
    user_expectations: Optional[List[str]] = Field(
        None, description="Non-negotiables — each max 200 chars"
    )

    @field_validator("user_expectations")
    @classmethod
    def validate_expectations(cls, v):
        if v:
            for item in v:
                if len(item) > 200:
                    raise ValueError("Each user expectation must be max 200 characters.")
        return v


class Step0SectionD(BaseModel):
    """Section D — Success Metrics & Expectations"""
    success_metrics: List[SuccessMetric] = Field(..., min_length=1)
    enterprise_expectations: Optional[str] = Field(None, max_length=500)
    definition_of_success: str = Field(
        ..., min_length=30, max_length=500,
        description="In your own words, what does a successful project outcome look like?"
    )


class Step0Input(BaseModel):
    section_a: Step0SectionA
    section_b: Step0SectionB
    section_c: Step0SectionC
    section_d: Step0SectionD

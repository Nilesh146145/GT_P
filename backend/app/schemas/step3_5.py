from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum
from datetime import date
from app.schemas.common import PriorityLevel, LikelihoodLevel, ImpactLevel, SeniorityLevel, Currency, PricingModel


# ══════════════════════════════════════════════
# STEP 3 — Integrations & User Management
# ══════════════════════════════════════════════

class IntegrationDirection(str, Enum):
    inbound = "Inbound"
    outbound = "Outbound"
    bidirectional = "Bidirectional"


class IntegrationProtocol(str, Enum):
    rest = "REST"
    graphql = "GraphQL"
    soap = "SOAP"
    webhook = "Webhook"
    file_based = "File-based"
    sdk = "SDK"


class IntegrationAuth(str, Enum):
    oauth2 = "OAuth 2.0"
    api_key = "API Key"
    saml = "SAML"
    basic = "Basic Auth"
    certificate = "Certificate"
    none = "None"


class DataFormat(str, Enum):
    json = "JSON"
    xml = "XML"
    csv = "CSV"
    binary = "Binary"


class SandboxProvider(str, Enum):
    client = "Client"
    glimmora = "GlimmoraTeam obtains"
    not_needed = "Not needed"


class ErrorHandlingSLA(str, Enum):
    same_day = "Same-day"
    four_hour = "4-hour"
    one_hour = "1-hour"
    custom = "Custom"


class ThirdPartyIntegration(BaseModel):
    integration_name: str = Field(..., max_length=100)
    direction: IntegrationDirection
    protocol: IntegrationProtocol
    authentication: IntegrationAuth
    data_format: DataFormat
    sandbox_credentials_by: SandboxProvider
    testing_responsibility: str = Field(
        ..., description="GlimmoraTeam / Client / Joint"
    )
    error_handling_sla: ErrorHandlingSLA
    error_handling_sla_custom: Optional[str] = None


class SSOProtocol(str, Enum):
    saml = "SAML 2.0"
    oidc = "OIDC"
    both = "Both"


class UserRegistrationModel(str, Enum):
    self_register = "Self-register"
    admin_only = "Admin-only"
    self_with_approval = "Self-register with admin approval"
    sso_only = "SSO only"


class CustomPasswordPolicy(BaseModel):
    min_length: int = Field(..., ge=6)
    complexity_requirements: str
    expiry_days: Optional[int] = None
    session_timeout_minutes: int = Field(..., ge=1)
    lockout_after_attempts: int = Field(..., ge=1)


class ScheduledJob(BaseModel):
    job_name: str = Field(..., max_length=100)
    frequency: str
    trigger_condition: str = Field(..., max_length=200)


class Step3SectionA(BaseModel):
    """Section A — Integration Specifications"""
    integrations: Optional[List[ThirdPartyIntegration]] = None


class Step3SectionB(BaseModel):
    """Section B — User Management Scope"""
    sso_required: bool = False
    sso_provider_name: Optional[str] = None
    sso_protocol: Optional[SSOProtocol] = None
    user_registration_model: Optional[UserRegistrationModel] = None
    use_custom_password_policy: bool = False
    custom_password_policy: Optional[CustomPasswordPolicy] = None
    user_action_audit_logging: bool = False
    audit_events: Optional[List[str]] = Field(
        None, description="login/logout / data access / record modifications / etc."
    )


class Step3SectionC(BaseModel):
    """Section C — Workflow Automation Scope"""
    approval_workflows_in_scope: bool = False
    approval_workflow_names: Optional[List[str]] = None
    notifications_in_scope: bool = False
    notification_events: Optional[List[str]] = None
    notification_channel: Optional[str] = Field(
        None, description="Email / Push / Both"
    )
    scheduled_jobs_in_scope: bool = False
    scheduled_jobs: Optional[List[ScheduledJob]] = None


class Step3Input(BaseModel):
    section_a: Step3SectionA
    section_b: Step3SectionB
    section_c: Step3SectionC


# ══════════════════════════════════════════════
# STEP 4 — Timeline, Team & Testing
# ══════════════════════════════════════════════

class PhasingStrategy(str, Enum):
    sequential = "Sequential phases"
    parallel = "Parallel workstreams"
    sprint_based = "Sprint-based (2-week sprints)"
    milestone_only = "Milestone-only"
    not_decided = "Not yet decided"


class TeamSize(str, Enum):
    size_1_3 = "1–3"
    size_4_8 = "4–8"
    size_9_15 = "9–15"
    size_16_25 = "16–25"
    size_25_plus = "25+"
    not_decided = "Not yet decided"


class WorkModel(str, Enum):
    fully_remote = "Fully remote"
    hybrid = "Hybrid"
    on_site = "On-site only"
    flexible = "Flexible"


class MilestoneEntry(BaseModel):
    name: str = Field(..., max_length=100)
    target_date: date
    acceptance_criteria: str = Field(..., min_length=50, description="Specific and testable")


class RequiredRole(BaseModel):
    role_name: str = Field(..., max_length=100)
    seniority: SeniorityLevel


class UATDetail(BaseModel):
    glimmora_support_level: str = Field(
        ..., description="Full support / Advisory only / Not included"
    )
    client_uat_resource: str = Field(..., min_length=20)
    uat_duration_days: int = Field(..., ge=1)
    signoff_authority_name: str = Field(..., description="Full name of UAT sign-off authority")
    signoff_authority_title: str = Field(..., description="Job title of UAT sign-off authority")


class DefectSLA(BaseModel):
    p1_critical_hours: int = Field(..., description="e.g. 4, 8, or 24")
    p2_high_days: int
    p3_medium_days: int
    p4_low: str = Field(..., description="Next release / No SLA")
    tracking_tool: str = Field(..., description="Jira / GitHub Issues / Azure DevOps / Other")


class Step4SectionA(BaseModel):
    """Section A — Timeline & Milestones"""
    start_date: date
    target_end_date: date
    phasing_strategy: Optional[PhasingStrategy] = None
    key_milestones: Optional[List[MilestoneEntry]] = None
    client_side_dependencies: Optional[List[str]] = None

    @field_validator("target_end_date")
    @classmethod
    def validate_dates(cls, v, info):
        start = info.data.get("start_date")
        if start and v <= start:
            raise ValueError("Target end date must be after start date.")
        if start and (v - start).days < 14:
            raise ValueError("Minimum project duration is 14 days.")
        return v


class Step4SectionB(BaseModel):
    """Section B — Team Requirements"""
    estimated_team_size: Optional[TeamSize] = None
    work_model: Optional[WorkModel] = None
    required_roles: List[RequiredRole] = Field(..., min_length=1)
    skill_priorities: Optional[str] = Field(None, max_length=500)
    knowledge_transfer_included: bool = False
    knowledge_transfer_scope: Optional[str] = Field(None, max_length=300)


class Step4SectionC(BaseModel):
    """Section C — Testing Scope"""
    unit_integration_coverage_target: str = Field(
        default="80%+", description="50% / 70% / 80%+ / Per project standards"
    )
    sit_in_scope: bool = False
    sit_ownership: Optional[str] = None
    sit_environment: Optional[str] = None
    sit_entry_criteria: Optional[str] = Field(None, max_length=200)
    sit_exit_criteria: Optional[str] = Field(None, max_length=200)

    uat: UATDetail

    pre_production_testing: bool = False
    pre_production_tests: Optional[List[str]] = None

    performance_testing_in_scope: bool = False
    performance_target_users: Optional[int] = None
    performance_target_response_ms_p95: Optional[int] = None
    performance_tool: Optional[str] = None
    performance_executor: Optional[str] = None

    security_testing_in_scope: bool = False
    owasp_scan: Optional[bool] = None
    penetration_testing: Optional[bool] = None
    pentest_performer: Optional[str] = None

    defect_sla: Optional[DefectSLA] = None


class Step4Input(BaseModel):
    section_a: Step4SectionA
    section_b: Step4SectionB
    section_c: Step4SectionC


# ══════════════════════════════════════════════
# STEP 5 — Budget & Risk
# ══════════════════════════════════════════════

class ContingencyBudget(str, Enum):
    pct_5 = "5%"
    pct_10 = "10%"
    pct_15 = "15%"
    pct_20 = "20%"
    custom = "Custom"


class EscalationProcess(str, Enum):
    glimmora_admin = "Direct to GlimmoraTeam Admin"
    client_executive = "Client executive"
    joint_committee = "Joint committee"
    not_defined = "Not defined"


class KnownRisk(BaseModel):
    description: str = Field(..., max_length=300)
    likelihood: LikelihoodLevel
    impact: ImpactLevel


class Step5SectionA(BaseModel):
    """Section A — Budget & Commercial"""
    budget_minimum: float = Field(..., gt=0)
    budget_maximum: float = Field(..., gt=0)
    currency: Currency = Currency.usd
    pricing_model: PricingModel = PricingModel.fixed_price
    budget_breakdown_preference: Optional[str] = Field(
        None, description="Milestone-based / Phase-based / Monthly / Fixed total only"
    )

    @field_validator("budget_maximum")
    @classmethod
    def validate_budget_max(cls, v, info):
        min_val = info.data.get("budget_minimum")
        if min_val and v < min_val:
            raise ValueError("Budget Maximum must be greater than or equal to Budget Minimum.")
        return v


class Step5SectionB(BaseModel):
    """Section B — Risk Parameters"""
    known_risks: List[KnownRisk] = Field(..., min_length=1)
    project_constraints: Optional[str] = Field(None, max_length=1000)
    contingency_budget: Optional[ContingencyBudget] = None
    contingency_custom_pct: Optional[float] = Field(None, ge=0, le=100)
    escalation_process: Optional[EscalationProcess] = None


class Step5Input(BaseModel):
    section_a: Step5SectionA
    section_b: Step5SectionB

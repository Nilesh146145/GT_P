from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum
from app.schemas.common import Industry, ProjectCategory, PlatformType, PriorityLevel


# ──────────────────────────────────────────────
# STEP 1 ENUMS
# ──────────────────────────────────────────────

class DataVolumeRange(str, Enum):
    under_10k = "< 10K rows"
    range_10k_1m = "10K–1M rows"
    range_1m_100m = "1M–100M rows"
    over_100m = "> 100M rows"
    volume_gb = "Volume in GB"


class MigrationApproach(str, Enum):
    one_time = "One-time cutover"
    incremental = "Incremental"
    ongoing_sync = "Ongoing sync"
    delta = "Delta"


class ResponsibleParty(str, Enum):
    client = "Client"
    glimmora = "GlimmoraTeam"
    both = "Both"
    third_party = "Third-party"


# ──────────────────────────────────────────────
# STEP 1 SUB-MODELS
# ──────────────────────────────────────────────

class FeatureModule(BaseModel):
    module_name: str = Field(..., max_length=100)
    description: str = Field(..., max_length=300, description="What this module must do")
    priority: PriorityLevel


class UserRole(BaseModel):
    role_name: str = Field(..., max_length=100)
    primary_actions: str = Field(..., max_length=200)


class WorkflowStep(BaseModel):
    step_number: int
    description: str = Field(..., max_length=100)


class KeyWorkflow(BaseModel):
    workflow_name: str = Field(..., max_length=100)
    steps: List[WorkflowStep] = Field(..., max_length=8)
    outcome: str = Field(..., max_length=200)


class DataMigrationScope(BaseModel):
    in_scope: bool
    source_system_name: Optional[str] = None
    estimated_data_volume: Optional[DataVolumeRange] = None
    volume_gb: Optional[float] = Field(None, description="Used when volume_range is 'Volume in GB'")
    migration_approach: Optional[MigrationApproach] = None
    source_extract_provided_by: Optional[ResponsibleParty] = None
    data_validation_responsibility: Optional[ResponsibleParty] = None
    rollback_plan_required: Optional[bool] = None


# ──────────────────────────────────────────────
# STEP 1 SECTIONS
# ──────────────────────────────────────────────

class Step1SectionA(BaseModel):
    """Section A — Project Identity"""
    project_title: str = Field(..., min_length=3, max_length=150)
    client_organisation: str = Field(..., min_length=2, max_length=100)
    industry: Industry
    industry_other: Optional[str] = Field(None, max_length=100)
    project_category: ProjectCategory
    platform_type: PlatformType
    platform_other: Optional[str] = Field(None, max_length=100)
    client_tech_landscape: Optional[str] = Field(None, max_length=500)

    @field_validator("industry_other")
    @classmethod
    def validate_industry_other(cls, v, info):
        if info.data.get("industry") == Industry.other and not v:
            raise ValueError("Please specify your industry type.")
        return v


class Step1SectionB(BaseModel):
    """Section B — Functional Requirements"""
    feature_modules: List[FeatureModule] = Field(..., min_length=2)
    user_roles: List[UserRole] = Field(..., min_length=1, max_length=20)
    key_workflows: List[KeyWorkflow] = Field(..., min_length=1)
    estimated_screen_count: Optional[int] = Field(None, ge=1, le=999)
    critical_business_rules: Optional[List[str]] = Field(None, description="Each max 200 chars")


class Step1SectionC(BaseModel):
    """Section C — Scope Boundaries"""
    out_of_scope_exclusions: List[str] = Field(
        ..., min_length=1, description="Each max 200 chars"
    )
    assumptions: Optional[List[str]] = None
    constraints: Optional[List[str]] = None
    data_migration: DataMigrationScope


class Step1Input(BaseModel):
    section_a: Step1SectionA
    section_b: Step1SectionB
    section_c: Step1SectionC


# ══════════════════════════════════════════════
# STEP 2 — Delivery & Technical Scope
# ══════════════════════════════════════════════

class UIUXScope(str, Enum):
    not_in_scope = "Not in scope"
    in_scope = "In scope"
    client_provides = "Client provides designs"


class DeploymentScope(str, Enum):
    not_in_scope = "Not in scope — working build handover only"
    cloud = "Deploy to cloud"
    on_premise = "Deploy to client on-premise"
    both = "Both"


class CloudProvider(str, Enum):
    aws = "AWS"
    azure = "Azure"
    gcp = "GCP"
    other = "Other"


class GoLiveScope(str, Enum):
    not_in_scope = "Not in scope"
    go_live_only = "Production go-live included"
    go_live_hypercare = "Go-live + post-go-live hypercare"


class HypercareDuration(str, Enum):
    one_week = "1 week"
    two_weeks = "2 weeks"
    one_month = "1 month"
    custom = "Custom"


class HypercareSupport(str, Enum):
    bugs_only = "Bug fixes only"
    bugs_and_minor = "Bug fixes + minor enhancements"


class DevelopmentScope(BaseModel):
    frontend: bool = False
    backend: bool = False
    api: bool = False
    database_design: bool = False
    third_party_integration: bool = False
    ci_cd_setup: bool = False

    @field_validator("frontend", mode="before")
    @classmethod
    def at_least_one_required(cls, v, info):
        return v


class UIUXDetail(BaseModel):
    scope: UIUXScope
    wireframes: bool = False
    high_fidelity_mockups: bool = False
    design_system: bool = False
    clickable_prototype: bool = False
    brand_identity: bool = False
    brand_guidelines_source: Optional[str] = Field(
        None, description="Client provides guidelines / GlimmoraTeam creates from scratch"
    )


class AWSServices(BaseModel):
    ec2_ecs_eks: bool = False
    rds_aurora: bool = False
    s3: bool = False
    cloudfront: bool = False
    lambda_: bool = False
    api_gateway: bool = False
    load_balancer: bool = False


class CloudDeploymentDetail(BaseModel):
    provider: CloudProvider
    containerisation_k8s: bool = False
    environments: List[str] = Field(
        default=[], description="Dev / Staging / Pre-Production / Production"
    )
    aws_services: Optional[AWSServices] = None


class OnPremiseDetail(BaseModel):
    server_installation: bool = False
    ssl_certificates: bool = False
    monitoring_alerting: bool = False
    backup_configuration: bool = False


class DeploymentDetail(BaseModel):
    scope: DeploymentScope
    cloud: Optional[CloudDeploymentDetail] = None
    on_premise: Optional[OnPremiseDetail] = None


class GoLiveDetail(BaseModel):
    scope: GoLiveScope
    hypercare_duration: Optional[HypercareDuration] = None
    hypercare_duration_custom: Optional[str] = None
    hypercare_support_level: Optional[HypercareSupport] = None


class Step2SectionA(BaseModel):
    """Section A — Delivery Scope Boundary"""
    development_scope: DevelopmentScope
    ui_ux: UIUXDetail
    deployment: DeploymentDetail
    go_live: GoLiveDetail

    @field_validator("development_scope")
    @classmethod
    def at_least_one_dev_scope(cls, v):
        fields = [v.frontend, v.backend, v.api, v.database_design,
                  v.third_party_integration, v.ci_cd_setup]
        if not any(fields):
            raise ValueError("At least one development scope item must be selected.")
        return v


class PerformanceRequirements(BaseModel):
    concurrent_users_target: Optional[int] = None
    response_time_sla_ms: Optional[int] = Field(
        None, description="Target response time in milliseconds"
    )
    expected_data_volume: Optional[str] = Field(
        None, description="Small < 1GB / Medium 1–100GB / Large 100GB+"
    )


class Step2SectionB(BaseModel):
    """Section B — Technical Architecture"""
    technology_stack: str = Field(
        ..., min_length=10, max_length=1000,
        description="Full specification e.g. React 18 + TypeScript, Node.js/NestJS..."
    )
    scalability_performance: Optional[PerformanceRequirements] = None


class ETLApproach(str, Enum):
    custom_scripts = "Custom scripts"
    aws_dms = "AWS DMS"
    talend = "Talend"
    azure_data_factory = "Azure Data Factory"
    manual = "Manual export-import"
    other = "Other"


class TransformationComplexity(str, Enum):
    no_transform = "No transformation (direct copy)"
    simple_mapping = "Simple field mapping"
    complex_logic = "Complex business logic"
    data_cleansing = "Data cleansing required"


class Step2SectionC(BaseModel):
    """Section C — Data Migration Technical (conditional on Step 1 migration in scope)"""
    etl_approach: Optional[ETLApproach] = None
    transformation_complexity: Optional[TransformationComplexity] = None
    data_validation_method: Optional[str] = Field(
        None, description="Automated validation scripts / Manual spot-check / Both"
    )


class Step2Input(BaseModel):
    section_a: Step2SectionA
    section_b: Step2SectionB
    section_c: Optional[Step2SectionC] = None

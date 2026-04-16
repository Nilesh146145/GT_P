from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum


# ══════════════════════════════════════════════
# STEP 6 — Quality Standards
# ══════════════════════════════════════════════

class SLAUptime(str, Enum):
    standard = "99.9%"
    high_availability = "99.95%"
    enterprise = "99.99%"
    custom = "Custom"
    not_applicable = "Not applicable"


class CodeReviewPolicy(str, Enum):
    peer_review = "Peer review before merge"
    lead_review = "Lead review only"
    no_formal = "No formal policy"
    not_applicable = "Not applicable"


class OfflineApproach(str, Enum):
    pwa = "PWA with service worker"
    local_caching = "Local caching"
    sync_on_reconnect = "Sync on reconnect"
    full_offline = "Full offline mode"


class LocalisationFormat(str, Enum):
    i18n_json = "i18n JSON files"
    cms_managed = "CMS-managed"
    hard_coded = "Hard-coded per build"


class BrowserCompatibility(BaseModel):
    chrome: bool = False
    chrome_min_version: Optional[str] = None
    firefox: bool = False
    safari: bool = False
    edge: bool = False
    ie11: bool = False
    all_modern: bool = False


class DeviceCompatibility(BaseModel):
    desktop: bool = False
    tablet: bool = False
    mobile: bool = False
    kiosk_pos: bool = False
    ios_min_version: Optional[str] = Field(None, description="e.g. iOS 14+")
    android_min_version: Optional[str] = Field(None, description="e.g. Android 10+")


class ReportingScope(BaseModel):
    in_scope: bool = False
    viewer_roles: Optional[List[str]] = None
    scheduled_reports: bool = False
    third_party_analytics: Optional[str] = Field(
        None, description="Google Analytics / Mixpanel / Custom / None"
    )
    export_formats: Optional[List[str]] = Field(
        None, description="CSV / Excel / PDF / API"
    )


class LocalisationScope(BaseModel):
    multi_language: bool = False
    languages: Optional[List[str]] = None
    format: Optional[LocalisationFormat] = None
    rtl_support: bool = False


class Step6Input(BaseModel):
    project_level_acceptance_criteria: str = Field(
        ..., min_length=30, max_length=3000,
        description="Global standards every deliverable must meet"
    )
    sla_uptime: Optional[SLAUptime] = None
    sla_uptime_custom: Optional[str] = None
    code_review_policy: Optional[CodeReviewPolicy] = None
    documentation_requirements: Optional[List[str]] = Field(
        None, description="Technical / User / Deployment / None / Custom"
    )
    browser_compatibility: BrowserCompatibility
    device_compatibility: DeviceCompatibility
    reporting_scope: Optional[ReportingScope] = None
    offline_support_required: bool = False
    offline_approach: Optional[OfflineApproach] = None
    offline_min_connectivity: Optional[str] = None
    localisation: Optional[LocalisationScope] = None

    @field_validator("browser_compatibility")
    @classmethod
    def at_least_one_browser(cls, v):
        if not any([v.chrome, v.firefox, v.safari, v.edge, v.ie11, v.all_modern]):
            raise ValueError("Please select at least one supported browser.")
        return v

    @field_validator("device_compatibility")
    @classmethod
    def at_least_one_device(cls, v):
        if not any([v.desktop, v.tablet, v.mobile, v.kiosk_pos]):
            raise ValueError("Please select at least one device type.")
        return v


# ══════════════════════════════════════════════
# STEP 7 — Governance & Compliance
# ══════════════════════════════════════════════

class LabourStandards(str, Enum):
    ilo = "ILO Core Labour Standards (international)"
    local = "Local jurisdiction regulations"
    custom = "Custom"
    not_applicable = "Not applicable"


class AccessibilityStandard(str, Enum):
    wcag_aa = "WCAG 2.1 Level AA"
    wcag_aaa = "WCAG 2.1 Level AAA"
    section_508 = "Section 508 (US government)"
    none = "None required"
    not_applicable = "Not applicable"


class DataSensitivity(str, Enum):
    public = "Public"
    internal = "Internal"
    confidential = "Confidential"
    restricted = "Restricted"


class EncryptionRequirement(str, Enum):
    standard_tls = "Standard TLS 1.3"
    end_to_end = "End-to-end required"
    at_rest_aes = "At-rest AES-256"
    both = "Both"
    custom = "Custom"


class AccessControlModel(str, Enum):
    rbac = "RBAC"
    abac = "ABAC"
    need_to_know = "Need-to-know only"
    no_special = "No special requirements"


class DataResidency(str, Enum):
    india_only = "India only"
    eu_only = "EU only"
    us_only = "US only"
    no_restriction = "No restriction"
    custom = "Custom"


class DPAStatus(str, Enum):
    required = "Yes"
    not_required = "No"
    already_in_place = "Already in place"


class PIAStatus(str, Enum):
    completed = "Completed"
    in_progress = "In progress"
    not_started = "Not started"
    not_required = "Not required"


class Step7SectionA(BaseModel):
    """Section A — Ethical Constraints"""
    non_discrimination_confirmed: bool = Field(
        ..., description="Must be True — hard block if False"
    )
    supplementary_commitments: Optional[str] = Field(None, max_length=500)
    labour_standards: LabourStandards
    labour_standards_custom: Optional[str] = Field(None, max_length=300)
    accessibility_requirements: Optional[AccessibilityStandard] = None
    prohibited_work_categories: Optional[List[str]] = Field(
        None, description="No surveillance / No dark pattern UX / etc."
    )

    @field_validator("non_discrimination_confirmed")
    @classmethod
    def must_confirm_non_discrimination(cls, v):
        if not v:
            raise ValueError(
                "The non-discrimination confirmation is mandatory for all SOWs on GlimmoraTeam. This cannot be skipped."
            )
        return v


class PersonalDataDetail(BaseModel):
    data_categories: List[str] = Field(
        ..., description="Name & contact details / Health records / Financial data / etc."
    )
    applicable_privacy_laws: List[str] = Field(
        ..., description="GDPR / PDPB / CCPA / etc."
    )
    dpa_required: DPAStatus
    dpa_reference_number: Optional[str] = None


class Step7SectionB(BaseModel):
    """Section B — Privacy Posture"""
    personal_data_involved: bool
    personal_data_detail: Optional[PersonalDataDetail] = None
    privacy_impact_assessment: Optional[PIAStatus] = None

    @field_validator("personal_data_detail")
    @classmethod
    def validate_personal_data_detail(cls, v, info):
        if info.data.get("personal_data_involved") and not v:
            raise ValueError(
                "Please specify applicable privacy law(s) and whether a Data Processing Agreement is required."
            )
        return v


class Step7SectionC(BaseModel):
    """Section C — Security & Compliance"""
    data_sensitivity_level: DataSensitivity = Field(
        ..., description="Public / Internal / Confidential / Restricted — NO DEFAULT"
    )
    encryption_requirements: Optional[EncryptionRequirement] = None
    regulatory_frameworks: Optional[List[str]] = Field(
        None, description="GDPR, SOC 2, ISO 27001, PCI-DSS, HIPAA, etc."
    )
    data_residency: Optional[DataResidency] = None
    data_residency_custom: Optional[str] = None
    access_control_model: Optional[AccessControlModel] = None


class Step7Input(BaseModel):
    section_a: Step7SectionA
    section_b: Step7SectionB
    section_c: Step7SectionC


# ══════════════════════════════════════════════
# STEP 8 — Commercial & Legal
# ══════════════════════════════════════════════

class IPOwnership(str, Enum):
    client_owns_all = "Client owns all IP and source code"
    glimmora_retains_framework = "GlimmoraTeam retains framework and component IP — client owns application layer"
    joint_ownership = "Joint ownership (defined in NDA)"
    custom = "Custom arrangement"


class RepoOwnership(str, Enum):
    client_owns_throughout = "Client owns and hosts the repository throughout delivery"
    glimmora_transfers_on_m3 = "GlimmoraTeam hosts during delivery, transfers to client on M3 payment"
    client_provides = "Client provides repository from day one"


class PortfolioRights(str, Enum):
    full_reference = "GlimmoraTeam may reference this project as portfolio work with client name"
    anonymous_reference = "GlimmoraTeam may reference this project without disclosing client name"
    no_reference = "No reference rights (strict NDA)"


class OSSPolicy(str, Enum):
    accepts_compatible = "Client accepts OSS components with compatible licences (MIT, Apache, BSD)"
    commercial_only = "All dependencies must have commercial licences — no OSS"
    custom = "Custom OSS policy"


class ThirdPartyLicensingModel(str, Enum):
    client_pays_all = "Client pays all third-party service and licence costs directly"
    glimmora_absorbs = "GlimmoraTeam absorbs all within project quote"
    split = "Split — GlimmoraTeam absorbs up to threshold, client pays above"


class WarrantyPeriod(str, Enum):
    days_30 = "30 days post go-live"
    days_60 = "60 days"
    days_90 = "90 days"
    months_6 = "6 months"
    custom = "Custom"
    no_warranty = "No warranty"


class PostWarrantyModel(str, Enum):
    not_included = "Not included"
    retainer = "Retainer (monthly fixed cost)"
    time_and_materials = "T&M (per-incident billing)"
    separate_contract = "Separate support contract (to be negotiated at go-live)"


class CRProcessModel(str, Enum):
    formal_cr = "All changes formally priced and approved before work begins"
    contingency_threshold = "Changes up to threshold included in contingency — above requires formal CR"
    t_and_m = "T&M for all changes above agreed baseline"


class PostWarrantyDetail(BaseModel):
    model: PostWarrantyModel
    monthly_cost: Optional[float] = None
    scope_description: Optional[str] = None
    p1_response_sla: Optional[str] = None
    p2_response_sla: Optional[str] = None
    p3_response_sla: Optional[str] = None
    support_channel: Optional[str] = None


class CRProcessDetail(BaseModel):
    model: CRProcessModel
    approver_name: Optional[str] = Field(None, description="Who approves from client side")
    approver_role: Optional[str] = None
    contingency_threshold_amount: Optional[float] = None


class Step8SectionA(BaseModel):
    """Section A — Intellectual Property & Rights"""
    ip_ownership: IPOwnership
    ip_ownership_custom_description: Optional[str] = Field(None, max_length=300)
    source_code_repo_ownership: RepoOwnership
    portfolio_reference_rights: PortfolioRights
    oss_policy: Optional[OSSPolicy] = None
    oss_policy_custom: Optional[str] = None


class Step8SectionB(BaseModel):
    """Section B — Financial & Operational Terms"""
    third_party_licensing: ThirdPartyLicensingModel
    third_party_licensing_threshold_amount: Optional[float] = Field(
        None, description="Used when model is 'split'"
    )
    warranty_period: WarrantyPeriod
    warranty_period_custom: Optional[str] = None
    post_warranty_support: Optional[PostWarrantyDetail] = None
    change_request_process: CRProcessDetail
    environment_running_costs: Optional[str] = Field(
        None, description="Client pays / GlimmoraTeam absorbs / Costs itemised monthly"
    )


class Step8Input(BaseModel):
    section_a: Step8SectionA
    section_b: Step8SectionB

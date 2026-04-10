"""
Shared Pydantic base models and project-wide enums.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── ORM base ──────────────────────────────────────────────────────────────────

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Generic responses ─────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class BaseResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[object] = None


# ── Session (used by auth schemas) ────────────────────────────────────────────

class SessionItem(BaseModel):
    id: str
    auth_method: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    expires_at: datetime


# ── Wizard / SOW status enums ─────────────────────────────────────────────────

class WizardStatus(str, Enum):
    draft = "draft"
    ready = "ready"
    submitted = "submitted"
    approved = "approved"
    generating = "generating"
    generated = "generated"
    completed = "completed"
    archived = "archived"


class SOWStatus(str, Enum):
    draft = "draft"
    in_review = "in_review"
    review = "review"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    changes_requested = "changes_requested"


# ── Project / industry enums (used by step1_2.py) ────────────────────────────

class Industry(str, Enum):
    fintech = "Fintech"
    healthtech = "Healthtech"
    edtech = "Edtech"
    ecommerce = "E-commerce / Retail"
    logistics = "Logistics / Supply Chain"
    real_estate = "Real Estate / PropTech"
    legaltech = "LegalTech"
    hrtech = "HR Tech"
    manufacturing = "Manufacturing"
    media = "Media / Entertainment"
    government = "Government / Public Sector"
    ngo = "NGO / Non-profit"
    hospitality = "Hospitality / Travel"
    agriculture = "Agriculture / AgriTech"
    energy = "Energy / CleanTech"
    other = "Other"


class ProjectCategory(str, Enum):
    new_product = "New product build"
    rebuild = "Rebuild / Re-platform"
    feature_expansion = "Feature expansion on existing product"
    mvp = "MVP / Proof of concept"
    integration = "Integration / API project"
    data_platform = "Data platform / Analytics"
    automation = "Process automation"
    migration = "System migration"
    other = "Other"


class PlatformType(str, Enum):
    web_app = "Web application"
    mobile_ios = "Mobile — iOS only"
    mobile_android = "Mobile — Android only"
    mobile_cross = "Mobile — Cross-platform (iOS + Android)"
    desktop = "Desktop application"
    web_and_mobile = "Web + Mobile"
    api_backend = "API / Backend only"
    data_pipeline = "Data pipeline / ETL"
    other = "Other"


class PriorityLevel(str, Enum):
    must_have = "Must Have"
    should_have = "Should Have"
    nice_to_have = "Nice to Have"
    out_of_scope = "Out of Scope"


# ── Risk / team enums (used by step3_5.py) ───────────────────────────────────

class LikelihoodLevel(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"


class ImpactLevel(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"
    critical = "Critical"


class SeniorityLevel(str, Enum):
    junior = "Junior"
    mid = "Mid-level"
    senior = "Senior"
    lead = "Lead"
    principal = "Principal / Staff"


class Currency(str, Enum):
    usd = "USD"
    inr = "INR"
    gbp = "GBP"
    eur = "EUR"
    aed = "AED"
    sgd = "SGD"


class PricingModel(str, Enum):
    fixed_price = "Fixed Price"
    time_and_materials = "Time & Materials"
    milestone_based = "Milestone-based"
    retainer = "Retainer"
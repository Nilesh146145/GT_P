"""
Registration schemas — derived from app/schemas/registration.py.
"""
from __future__ import annotations


from typing import List, Optional

from pydantic import BaseModel, EmailStr


class ContributorRegistrationStartRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    contributor_type: str
    dob: str
    country: str


class ContributorRegistrationCompleteRequest(BaseModel):
    registration_id: str
    phone: str
    verification_email: EmailStr
    timezone: str
    department_category: str
    department_other: Optional[str] = None
    availability_hours: int
    degree: Optional[str] = None
    branch: Optional[str] = None
    linkedin: Optional[str] = None
    mentor_ack: bool
    primary_skills: List[str]
    secondary_skills: List[str] = []
    other_skills: List[str] = []
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    career_stage: Optional[str] = None
    years_experience: Optional[str] = None
    resume_file_id: Optional[str] = None
    accept_tos: bool
    accept_coc: bool
    accept_dpa: bool
    accept_fee: bool
    accept_ahp: bool
    marketing_opt_in: bool = False


class EnterpriseRegistrationStartRequest(BaseModel):
    org_name: str
    org_type: str
    industry: str
    company_size: str
    founded_year: Optional[int] = None
    website: Optional[str] = None
    tagline: Optional[str] = None
    hq_country: str
    hq_city: Optional[str] = None


class EnterpriseRegistrationCompleteRequest(BaseModel):
    registration_id: str
    admin_first_name: str
    admin_last_name: str
    admin_title: str
    admin_email: EmailStr
    admin_department: Optional[str] = None
    admin_linkedin: Optional[str] = None
    phone: str
    password: str
    mfa_method: str
    accept_tos: bool
    accept_privacy_policy: bool
    accept_esa: bool
    accept_ahp: bool
    marketing_opt_in: bool = False


class RegistrationStartResponse(BaseModel):
    registration_id: str
    next_step: str


class RegistrationCompleteResponse(BaseModel):
    entity_id: str
    status: str
    next_step: str

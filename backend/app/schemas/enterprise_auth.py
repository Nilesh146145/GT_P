"""
Enterprise auth schemas — derived from app/schemas/enterprise_auth.py.
"""
from __future__ import annotations


from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.auth import AuthUser


def _validate_password(v: str) -> str:
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 characters (bcrypt limit)")
    return v


class EnterpriseRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")

    org_name: str = Field(alias="orgName")
    org_type: str = Field(alias="orgType")
    org_type_other: Optional[str] = Field(default=None, alias="orgTypeOther")
    industry: str
    industry_other: Optional[str] = Field(default=None, alias="industryOther")
    company_size: str = Field(alias="companySize")
    website: Optional[str] = None
    hq_country: Optional[str] = Field(default=None, alias="hqCountry")
    hq_city: Optional[str] = Field(default=None, alias="hqCity")

    admin_title: str = Field(alias="adminTitle")
    admin_dept: Optional[str] = Field(default=None, alias="adminDept")
    incorporation_country: Optional[str] = Field(default=None, alias="incorporationCountry")
    incorporation_file_key: Optional[str] = Field(default=None, alias="incorporationFileKey")

    phone: Optional[str] = None
    accept_tos: bool = Field(default=False, alias="acceptTos")
    accept_pp: bool = Field(default=False, alias="acceptPp")
    accept_esa: bool = Field(default=False, alias="acceptEsa")
    accept_ahp: bool = Field(default=False, alias="acceptAhp")
    marketing_opt_in: bool = Field(default=False, alias="marketingOptIn")

    model_config = {"populate_by_name": True}

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, v: str) -> str:
        return _validate_password(v)


class EnterpriseRegisterResponse(BaseModel):
    user: AuthUser
    enterprise_profile_id: str


class EnterpriseCompanyProfile(BaseModel):
    """Company details for enterprise users on GET /auth/me (profile section)."""

    enterprise_profile_id: str = Field(alias="enterpriseProfileId")
    org_name: str = Field(default="", alias="orgName")
    org_type: str = Field(default="", alias="orgType")
    org_type_other: Optional[str] = Field(default=None, alias="orgTypeOther")
    industry: str = ""
    industry_other: Optional[str] = Field(default=None, alias="industryOther")
    company_size: str = Field(default="", alias="companySize")
    website: Optional[str] = None
    hq_country: Optional[str] = Field(default=None, alias="hqCountry")
    hq_city: Optional[str] = Field(default=None, alias="hqCity")
    admin_title: str = Field(default="", alias="adminTitle")
    admin_dept: Optional[str] = Field(default=None, alias="adminDept")
    incorporation_country: Optional[str] = Field(default=None, alias="incorporationCountry")

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

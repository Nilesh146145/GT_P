"""
Enterprise auth schemas — derived from app/schemas/enterprise_auth.py.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.auth import AuthUser


def _validate_password(v: str) -> str:
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 characters (bcrypt limit)")
    return v


class EnterpriseRegisterRequest(BaseModel):
    """Full signup body for ``POST /auth/register`` and ``POST /auth/register/enterprise`` (camelCase JSON)."""

    email: EmailStr
    password: str = Field(min_length=12)
    first_name: str = Field(validation_alias="firstName")
    last_name: str = Field(validation_alias="lastName")

    org_name: str = Field(validation_alias="orgName")
    org_type: str = Field(validation_alias="orgType")
    org_type_other: Optional[str] = Field(default=None, validation_alias="orgTypeOther")
    industry: str
    industry_other: Optional[str] = Field(default=None, validation_alias="industryOther")
    company_size: str = Field(validation_alias="companySize")
    website: Optional[str] = None
    hq_country: Optional[str] = Field(default=None, validation_alias="hqCountry")
    hq_city: Optional[str] = Field(default=None, validation_alias="hqCity")

    admin_title: str = Field(validation_alias="adminTitle")
    admin_dept: Optional[str] = Field(default=None, validation_alias="adminDept")
    incorporation_country: Optional[str] = Field(default=None, validation_alias="incorporationCountry")
    incorporation_file_key: Optional[str] = Field(default=None, validation_alias="incorporationFileKey")

    phone: Optional[str] = None
    accept_tos: bool = Field(default=False, validation_alias="acceptTos")
    accept_pp: bool = Field(default=False, validation_alias="acceptPp")
    accept_esa: bool = Field(default=False, validation_alias="acceptEsa")
    accept_ahp: bool = Field(default=False, validation_alias="acceptAhp")
    marketing_opt_in: bool = Field(default=False, validation_alias="marketingOptIn")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "email": "demo@example.com",
                "password": "TestPassword12",
                "firstName": "Demo",
                "lastName": "User",
                "orgName": "Demo Org Ltd",
                "orgType": "Private Limited",
                "orgTypeOther": None,
                "industry": "Technology",
                "industryOther": None,
                "companySize": "1-50",
                "website": "https://example.com",
                "hqCountry": "IN",
                "hqCity": "Bengaluru",
                "adminTitle": "IT Director",
                "adminDept": "Technology",
                "incorporationCountry": "IN",
                "incorporationFileKey": "uploads/test-cert.pdf",
                "phone": "+919999999999",
                "acceptTos": True,
                "acceptPp": True,
                "acceptEsa": True,
                "acceptAhp": True,
                "marketingOptIn": False,
            }
        },
    )

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, v: str) -> str:
        return _validate_password(v)

    @model_validator(mode="after")
    def legal_acceptances_required(self):
        if not all(
            (self.accept_tos, self.accept_pp, self.accept_esa, self.accept_ahp)
        ):
            raise ValueError(
                "acceptTos, acceptPp, acceptEsa, and acceptAhp must all be true to register."
            )
        return self

    @model_validator(mode="after")
    def other_industry_and_org_type(self):
        if (self.industry or "").strip().lower() == "other":
            if not (self.industry_other or "").strip():
                raise ValueError('industryOther is required when industry is "Other".')
        if (self.org_type or "").strip().lower() == "other":
            if not (self.org_type_other or "").strip():
                raise ValueError('orgTypeOther is required when orgType is "Other".')
        return self


class EnterpriseRegisterResponse(BaseModel):
    user: AuthUser
    enterprise_profile_id: str

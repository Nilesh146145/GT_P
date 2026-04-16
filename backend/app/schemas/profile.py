"""
Profile schemas for self-service profile editing and profile picture updates.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _strip_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class ContributorProfileUpdate(BaseModel):
    contributor_type: Optional[str] = Field(default=None, alias="contributorType")
    country_of_residence: Optional[str] = Field(default=None, alias="countryOfResidence", max_length=120)
    date_of_birth: Optional[date] = Field(default=None, alias="dateOfBirth")
    time_zone: Optional[str] = Field(default=None, alias="timeZone", max_length=80)
    weekly_availability_hours: Optional[int] = Field(default=None, alias="weeklyAvailabilityHours", ge=1, le=168)
    department_category: Optional[str] = Field(default=None, alias="departmentCategory", max_length=120)
    department_other: Optional[str] = Field(default=None, alias="departmentOther", max_length=240)
    degree_qualification: Optional[str] = Field(default=None, alias="degreeQualification", max_length=240)
    primary_skills: Optional[list[str]] = Field(default=None, alias="primarySkills")
    secondary_skills: Optional[list[str]] = Field(default=None, alias="secondarySkills")
    other_skills: Optional[list[str]] = Field(default=None, alias="otherSkills")
    linkedin_url: Optional[str] = Field(default=None, alias="linkedinUrl", max_length=500)
    nda_signatory_legal_name: Optional[str] = Field(default=None, alias="ndaSignatoryLegalName", max_length=240)
    verification_email: Optional[EmailStr] = Field(default=None, alias="verificationEmail")
    resume_file_key: Optional[str] = Field(default=None, alias="resumeFileKey", max_length=512)
    notify_new_tasks_opt_in: Optional[bool] = Field(default=None, alias="notifyNewTasksOptIn")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator(
        "country_of_residence",
        "time_zone",
        "department_category",
        "department_other",
        "degree_qualification",
        "linkedin_url",
        "nda_signatory_legal_name",
        "resume_file_key",
        mode="before",
    )
    @classmethod
    def strip_optional_strings(cls, value):
        if value is None:
            return value
        if not isinstance(value, str):
            raise ValueError("Must be a string")
        return _strip_optional(value)

    @field_validator("primary_skills", "secondary_skills", "other_skills", mode="before")
    @classmethod
    def clean_skill_lists(cls, value):
        if value is None:
            return value
        if not isinstance(value, list):
            raise ValueError("Must be a list of strings")
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned

    @field_validator("primary_skills")
    @classmethod
    def primary_skills_not_empty_if_provided(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is not None and not value:
            raise ValueError("primarySkills cannot be empty when provided")
        return value


class EnterpriseProfileUpdate(BaseModel):
    org_name: Optional[str] = Field(default=None, alias="orgName")
    org_type: Optional[str] = Field(default=None, alias="orgType")
    org_type_other: Optional[str] = Field(default=None, alias="orgTypeOther")
    industry: Optional[str] = None
    industry_other: Optional[str] = Field(default=None, alias="industryOther")
    company_size: Optional[str] = Field(default=None, alias="companySize")
    website: Optional[str] = None
    hq_country: Optional[str] = Field(default=None, alias="hqCountry")
    hq_city: Optional[str] = Field(default=None, alias="hqCity")
    admin_title: Optional[str] = Field(default=None, alias="adminTitle")
    admin_dept: Optional[str] = Field(default=None, alias="adminDept")
    incorporation_country: Optional[str] = Field(default=None, alias="incorporationCountry")
    incorporation_file_key: Optional[str] = Field(default=None, alias="incorporationFileKey")
    marketing_opt_in: Optional[bool] = Field(default=None, alias="marketingOptIn")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator(
        "org_name",
        "org_type",
        "org_type_other",
        "industry",
        "industry_other",
        "company_size",
        "website",
        "hq_country",
        "hq_city",
        "admin_title",
        "admin_dept",
        "incorporation_country",
        "incorporation_file_key",
        mode="before",
    )
    @classmethod
    def strip_optional_strings(cls, value):
        if value is None:
            return value
        if not isinstance(value, str):
            raise ValueError("Must be a string")
        return _strip_optional(value)


class UpdateMyProfileRequest(BaseModel):
    first_name: Optional[str] = Field(default=None, alias="firstName", max_length=120)
    last_name: Optional[str] = Field(default=None, alias="lastName", max_length=120)
    phone: Optional[str] = Field(default=None, alias="phoneNumber", max_length=32)
    contributor_profile: Optional[ContributorProfileUpdate] = Field(default=None, alias="contributorProfile")
    enterprise_profile: Optional[EnterpriseProfileUpdate] = Field(default=None, alias="enterpriseProfile")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("first_name", "last_name", "phone", mode="before")
    @classmethod
    def strip_text_fields(cls, value):
        if value is None:
            return value
        if not isinstance(value, str):
            raise ValueError("Must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty")
        return stripped

"""
Contributor registration — full profile + legal acknowledgments (MFA optional).
"""
from __future__ import annotations


from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.auth import AuthUser


def _validate_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 characters (bcrypt limit)")
    return v


class ContributorType(str, Enum):
    student = "student"
    women_workforce = "women_workforce"
    general_workforce = "general_workforce"


class ContributorRegisterRequest(BaseModel):
    """All optional-at-UX fields are optional in JSON except where noted; legal flags must be true."""

    first_name: str = Field(alias="firstName", min_length=1, max_length=120)
    last_name: str = Field(alias="lastName", min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    confirm_password: str = Field(alias="confirmPassword", min_length=8)

    contributor_type: ContributorType = Field(alias="contributorType")
    country_of_residence: str = Field(alias="countryOfResidence", min_length=1, max_length=120)
    date_of_birth: date = Field(alias="dateOfBirth")
    time_zone: str = Field(alias="timeZone", min_length=1, max_length=80)
    weekly_availability_hours: int = Field(alias="weeklyAvailabilityHours", ge=1, le=168)
    department_category: str = Field(alias="departmentCategory", min_length=1, max_length=120)
    department_other: Optional[str] = Field(default=None, alias="departmentOther", max_length=240)

    degree_qualification: Optional[str] = Field(default=None, alias="degreeQualification", max_length=240)
    primary_skills: List[str] = Field(alias="primarySkills", min_length=1)
    secondary_skills: Optional[List[str]] = Field(default=None, alias="secondarySkills")
    other_skills: Optional[List[str]] = Field(default=None, alias="otherSkills")
    linkedin_url: Optional[str] = Field(default=None, alias="linkedinUrl", max_length=500)

    mentor_guide_acknowledged: bool = Field(alias="mentorGuideAcknowledged")
    nda_signatory_legal_name: str = Field(alias="ndaSignatoryLegalName", min_length=1, max_length=240)

    phone: str = Field(min_length=5, max_length=32)
    verification_email: Optional[EmailStr] = Field(default=None, alias="verificationEmail")
    resume_file_key: Optional[str] = Field(default=None, alias="resumeFileKey", max_length=512)

    accept_terms_of_use: bool = Field(alias="acceptTermsOfUse")
    accept_code_of_conduct: bool = Field(alias="acceptCodeOfConduct")
    accept_privacy_policy: bool = Field(alias="acceptPrivacyPolicy")
    accept_harassment_policy: bool = Field(alias="acceptHarassmentPolicy")
    acknowledgments_accepted: bool = Field(alias="acknowledgmentsAccepted")
    notify_new_tasks_opt_in: bool = Field(alias="notifyNewTasksOptIn")

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    @field_validator("password", "confirm_password")
    @classmethod
    def password_limits(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("primary_skills")
    @classmethod
    def primary_skills_non_empty_strings(cls, v: List[str]) -> List[str]:
        out = [s.strip() for s in v if s and str(s).strip()]
        if not out:
            raise ValueError("primarySkills must contain at least one non-empty skill")
        return out

    @field_validator("secondary_skills", "other_skills", mode="before")
    @classmethod
    def optional_skill_lists(cls, v):
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("Must be a list of strings")
        return [str(s).strip() for s in v if s is not None and str(s).strip()]

    @model_validator(mode="after")
    def validate_registration(self) -> "ContributorRegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("confirmPassword must match password")

        if not self.accept_terms_of_use:
            raise ValueError("acceptTermsOfUse must be true")
        if not self.accept_code_of_conduct:
            raise ValueError("acceptCodeOfConduct must be true")
        if not self.accept_privacy_policy:
            raise ValueError("acceptPrivacyPolicy must be true")
        if not self.accept_harassment_policy:
            raise ValueError("acceptHarassmentPolicy must be true")
        if not self.mentor_guide_acknowledged:
            raise ValueError("mentorGuideAcknowledged must be true")
        if not self.acknowledgments_accepted:
            raise ValueError("acknowledgmentsAccepted must be true")

        dc = self.department_category.strip().lower()
        if dc == "other" and not (self.department_other and self.department_other.strip()):
            raise ValueError("departmentOther is required when departmentCategory is Other")

        if not self.nda_signatory_legal_name.strip():
            raise ValueError("ndaSignatoryLegalName must be a non-empty full legal name")

        return self

    def effective_verification_email(self) -> str:
        return (self.verification_email or self.email).lower()


class ContributorRegisterResponse(BaseModel):
    user: AuthUser

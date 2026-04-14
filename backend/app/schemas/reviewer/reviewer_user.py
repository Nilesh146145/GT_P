from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator


class ReviewerLifecycleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INVITED = "INVITED"
    EXPIRED = "EXPIRED"


class CreateReviewerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        alias="firstName",
        validation_alias=AliasChoices("firstName", "first_name"),
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        alias="lastName",
        validation_alias=AliasChoices("lastName", "last_name"),
    )
    job_title: str = Field(
        ...,
        min_length=1,
        max_length=120,
        alias="role",
        validation_alias=AliasChoices("role", "jobTitle", "job_title"),
    )
    designation: str = Field(..., min_length=1, max_length=200)
    department: str = Field(..., min_length=1, max_length=200)
    username: str = Field(..., min_length=1, max_length=120)
    language: str = Field(..., min_length=2, max_length=32)
    time_zone: str = Field(
        ...,
        min_length=1,
        max_length=120,
        alias="timeZone",
        validation_alias=AliasChoices("timeZone", "time_zone"),
    )
    lifecycle_status: ReviewerLifecycleStatus = Field(
        default=ReviewerLifecycleStatus.INVITED,
        alias="status",
        validation_alias=AliasChoices("status", "lifecycle_status", "lifecycleStatus"),
    )

    @field_validator("lifecycle_status", mode="before")
    @classmethod
    def coerce_lifecycle(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized in ("ACTIVE", "INVITED", "EXPIRED"):
                return ReviewerLifecycleStatus[normalized]
        return value

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("username must not be empty")
        return normalized


class CreateReviewerResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: EmailStr
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    job_title: str = Field(alias="jobTitle")
    designation: str
    department: str
    username: str
    language: str
    time_zone: str = Field(alias="timeZone")
    lifecycle_status: ReviewerLifecycleStatus = Field(alias="status")
    role: str = "reviewer"
    requires_password_change: bool = Field(default=True, alias="requiresPasswordChange")
    is_first_login: bool = Field(default=True, alias="isFirstLogin")
    temporary_password: str = Field(alias="temporaryPassword")


class CreateReviewerUserApiResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: CreateReviewerResponse


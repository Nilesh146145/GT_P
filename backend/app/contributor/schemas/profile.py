from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SkillItem(BaseModel):
    name: str
    proficiency: str | int | float | None = None


class SkillsPutBody(BaseModel):
    skills: list[SkillItem] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    display_name: str | None = None
    anonymous_id: str | None = None
    avatar: str | None = None
    email: str | None = None
    phone: str | None = None
    track: str | None = None
    verification_status: str | None = None
    joined_at: datetime | None = None
    profile_completeness: float | None = None
    timezone: str | None = None
    weekly_hours: float | int | None = None
    availability: str | None = None
    language: str | None = None
    bio: str | None = None
    country: str | None = None
    city: str | None = None
    skills: list[SkillItem] = Field(default_factory=list)


class ProfilePatchBody(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    phone: str | None = None
    country: str | None = None
    city: str | None = None
    timezone: str | None = None
    weekly_hours: float | int | None = None
    availability: str | None = None
    language: str | None = None

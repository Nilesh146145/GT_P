from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

EvidenceType = Literal["link", "file", "github"]


class EvidenceSkillRef(BaseModel):
    name: str
    proficiency: str | int | float | None = None


class EvidenceCreate(BaseModel):
    title: str
    type: EvidenceType
    url: str | None = None
    file_id: str | None = None
    description: str | None = None
    skills: list[EvidenceSkillRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_url_or_file(self) -> EvidenceCreate:
        if self.type in ("link", "github"):
            if not self.url or not self.url.strip():
                raise ValueError("url is required for type link or github")
        elif self.type == "file":
            if not self.file_id or not str(self.file_id).strip():
                raise ValueError("file_id is required for type file")
        return self


class EvidenceUpdate(BaseModel):
    title: str | None = None
    type: EvidenceType | None = None
    url: str | None = None
    file_id: str | None = None
    description: str | None = None
    skills: list[EvidenceSkillRef] | None = None

    @model_validator(mode="after")
    def validate_type_requirements(self) -> EvidenceUpdate:
        t = self.type
        if t is None:
            return self
        if t in ("link", "github"):
            if self.url is not None and not str(self.url).strip():
                raise ValueError("url cannot be empty for type link or github")
        elif t == "file":
            if self.file_id is not None and not str(self.file_id).strip():
                raise ValueError("file_id cannot be empty for type file")
        return self


class EvidenceResponse(BaseModel):
    id: str
    title: str
    type: EvidenceType
    url: str | None = None
    file_id: str | None = None
    description: str | None = None
    skills: list[EvidenceSkillRef] = Field(default_factory=list)


class EvidenceListResponse(BaseModel):
    items: list[EvidenceResponse]
    total: int

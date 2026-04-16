from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SenderRole(str, Enum):
    ai_assistant = "ai_assistant"
    project_team = "project_team"
    mentor = "mentor"


class ThreadRoleFilter(str, Enum):
    all = "all"
    ai_assistant = "ai_assistant"
    project_team = "project_team"
    mentor = "mentor"


class RatingValue(str, Enum):
    up = "up"
    down = "down"


class ThreadListItem(BaseModel):
    id: str
    sender_name: str
    sender_role: SenderRole
    project_name: str
    task_id: str | None = None
    task_title: str | None = None
    last_message: str
    timestamp: datetime
    unread: bool
    unread_count: int = Field(ge=0)
    avatar: str | None = None


class ThreadListResponse(BaseModel):
    items: list[ThreadListItem]
    page: int
    page_size: int
    total: int


class Participant(BaseModel):
    id: str
    name: str
    role: SenderRole
    avatar: str | None = None


class MessageInThread(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    sender_role: SenderRole
    content: str
    timestamp: datetime
    attachment_ids: list[str] = Field(default_factory=list)
    rating: Literal["up", "down"] | None = None


class ThreadDetail(BaseModel):
    id: str
    participants: list[Participant]
    task_id: str | None = None
    project_name: str
    messages: list[MessageInThread]


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    attachment_ids: list[str] = Field(default_factory=list)


class MessageRatingBody(BaseModel):
    rating: RatingValue

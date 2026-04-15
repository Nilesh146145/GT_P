from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TicketCategory(str, Enum):
    technical = "technical"
    account = "account"
    task_question = "task_question"
    payment = "payment"
    safety = "safety"


class TicketPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class TicketStatus(str, Enum):
    open = "open"
    pending = "pending"
    in_progress = "in_progress"
    waiting_on_user = "waiting_on_user"
    resolved = "resolved"
    closed = "closed"


class GrievanceCategory(str, Enum):
    review_dispute = "review_dispute"
    payment_dispute = "payment_dispute"
    unfair_treatment = "unfair_treatment"
    accessibility = "accessibility"
    other = "other"


class SafetyCategory(str, Enum):
    harassment = "harassment"
    threatening = "threatening"
    inappropriate = "inappropriate"
    discrimination = "discrimination"
    fraud = "fraud"
    other = "other"


# --- FAQs ---


class FAQItem(BaseModel):
    id: str
    category: str
    question: str
    answer: str


class FAQListResponse(BaseModel):
    items: list[FAQItem]
    total: int


# --- Tickets ---


class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=1)
    category: TicketCategory
    priority: TicketPriority
    description: str = Field(..., min_length=1)
    attachment_ids: list[str] = Field(default_factory=list)
    related_task_id: str | None = None
    related_project_id: str | None = None


class TicketMessageCreate(BaseModel):
    message: str = Field(..., min_length=1)
    attachment_ids: list[str] = Field(default_factory=list)


class TicketMessage(BaseModel):
    id: str
    author: str
    message: str
    attachment_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class TicketListItem(BaseModel):
    id: str
    subject: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    created_at: datetime
    updated_at: datetime


class TicketDetail(BaseModel):
    id: str
    subject: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    description: str
    attachment_ids: list[str] = Field(default_factory=list)
    related_task_id: str | None = None
    related_project_id: str | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[TicketMessage] = Field(default_factory=list)


class PaginatedTickets(BaseModel):
    items: list[TicketListItem]
    page: int
    page_size: int
    total: int


# --- Grievances ---


class GrievanceCreate(BaseModel):
    category: GrievanceCategory
    subject: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    related_reference: str | None = None
    anonymous: bool = False
    attachment_ids: list[str] = Field(default_factory=list)


class GrievanceListItem(BaseModel):
    id: str
    category: GrievanceCategory
    subject: str
    status: str
    created_at: datetime
    anonymous: bool


class GrievanceDetail(BaseModel):
    id: str
    category: GrievanceCategory
    subject: str
    description: str
    related_reference: str | None = None
    anonymous: bool
    attachment_ids: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime


class GrievanceListResponse(BaseModel):
    items: list[GrievanceListItem]
    total: int


# --- Safety reports ---


class SafetyReportCreate(BaseModel):
    category: SafetyCategory
    description: str = Field(..., min_length=1)
    related_reference: str | None = None
    attachment_ids: list[str] = Field(default_factory=list)


class SafetyReportResponse(BaseModel):
    id: str
    category: SafetyCategory
    description: str
    related_reference: str | None = None
    attachment_ids: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime

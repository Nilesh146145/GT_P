from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExceptionType(str, Enum):
    SLA_BREACH = "SLA_BREACH"
    DELAY_RISK = "DELAY_RISK"
    QUALITY_ISSUE = "QUALITY_ISSUE"
    PAYMENT_BLOCKER = "PAYMENT_BLOCKER"
    DEPENDENCY_BLOCK = "DEPENDENCY_BLOCK"


class ExceptionSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExceptionStatus(str, Enum):
    OPEN = "OPEN"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"


class ProjectException(BaseModel):
    id: str
    project_id: str
    type: ExceptionType
    severity: ExceptionSeverity
    status: ExceptionStatus
    title: str
    detail: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    escalation_id: str | None = None


class ExceptionCreateRequest(BaseModel):
    type: ExceptionType
    severity: ExceptionSeverity
    title: str = Field(min_length=1)
    detail: str | None = None


class ExceptionsResponse(BaseModel):
    project_id: str
    exceptions: list[ProjectException]


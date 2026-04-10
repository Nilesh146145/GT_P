from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskExecutionStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"


class TeamTaskItem(BaseModel):
    task_id: str
    task_title: str
    contributors: list[str] = Field(description="Assigned people for this task")
    skills: list[str] = Field(description="Skills required or applied")
    execution_status: TaskExecutionStatus


class TeamCompositionResponse(BaseModel):
    project_id: str
    tasks: list[TeamTaskItem]


class SkillCoverageRow(BaseModel):
    skill: str
    task_count: int = Field(description="Number of tasks that require this skill")


class SkillCoverageResponse(BaseModel):
    project_id: str
    skills: list[SkillCoverageRow]


class SkillReviewRequestBody(BaseModel):
    note: str | None = Field(default=None, description="Optional message to Admin")


class SkillReviewRequestResponse(BaseModel):
    request_id: str
    project_id: str
    status: str = "submitted"
    created_at: datetime
    message: str

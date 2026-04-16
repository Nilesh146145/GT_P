from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RecommendationType(str, Enum):
    task_based = "task_based"
    skill_based = "skill_based"


class LearningRecommendation(BaseModel):
    id: str
    type: RecommendationType
    title: str
    skill: str
    reason: str
    difficulty: str
    estimated_hours: float = Field(ge=0)
    resource_url: Optional[str] = None
    related_task_id: Optional[str] = None
    priority: str
    recommended_at: datetime


class DismissResponse(BaseModel):
    recommendation_id: str
    dismissed: bool = True


class MarkOpenedResponse(BaseModel):
    recommendation_id: str
    opened: bool = True

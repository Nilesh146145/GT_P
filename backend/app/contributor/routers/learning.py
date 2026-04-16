from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status

from app.contributor.schemas.learning import (
    DismissResponse,
    LearningRecommendation,
    MarkOpenedResponse,
    RecommendationType,
)
from app.contributor.dependencies import get_contributor_id
from app.contributor.services.learning_store import store

router = APIRouter(
    prefix="/api/contributor/learning",
    tags=["learning"],
    dependencies=[Depends(get_contributor_id)],
)


@router.get(
    "/recommendations",
    response_model=list[LearningRecommendation],
)
def list_recommendations(
    type: Annotated[
        Optional[RecommendationType],
        Query(description="Filter by recommendation source type"),
    ] = None,
    priority: Annotated[
        Optional[str],
        Query(description="Filter by priority label"),
    ] = None,
    skill: Annotated[
        Optional[str],
        Query(description="Filter by skill name (substring match)"),
    ] = None,
) -> list[LearningRecommendation]:
    """Learning suggestions; optional filters: type, priority, skill."""
    return store.list_filtered(type_=type, priority=priority, skill=skill)


@router.post(
    "/recommendations/{recommendation_id}/dismiss",
    response_model=DismissResponse,
    status_code=status.HTTP_200_OK,
)
def dismiss_recommendation(recommendation_id: str) -> DismissResponse:
    return store.dismiss(recommendation_id)


@router.post(
    "/recommendations/{recommendation_id}/mark-opened",
    response_model=MarkOpenedResponse,
    status_code=status.HTTP_200_OK,
)
def mark_recommendation_opened(recommendation_id: str) -> MarkOpenedResponse:
    return store.mark_opened(recommendation_id)

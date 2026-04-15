"""Learning recommendations in-memory store."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.contributor.schemas.learning import (
    DismissResponse,
    LearningRecommendation,
    MarkOpenedResponse,
    RecommendationType,
)


class LearningStore:
    def __init__(self) -> None:
        self._recommendations: dict[str, LearningRecommendation] = {}
        self._dismissed: set[str] = set()
        self._opened: set[str] = set()

    def _seed_if_empty(self) -> None:
        if self._recommendations:
            return
        now = datetime.now(timezone.utc)
        samples = [
            LearningRecommendation(
                id="rec_001",
                type=RecommendationType.task_based,
                title="Complete onboarding checklist",
                skill="Project workflow",
                reason="Required before your first assigned task.",
                difficulty="beginner",
                estimated_hours=1.5,
                resource_url="https://example.com/learn/onboarding",
                related_task_id="tsk_001",
                priority="high",
                recommended_at=now,
            ),
            LearningRecommendation(
                id="rec_002",
                type=RecommendationType.skill_based,
                title="Async Python patterns",
                skill="Python",
                reason="Improves reliability of contributor automation.",
                difficulty="intermediate",
                estimated_hours=3.0,
                resource_url="https://example.com/learn/async-py",
                related_task_id=None,
                priority="medium",
                recommended_at=now,
            ),
        ]
        for r in samples:
            self._recommendations[r.id] = r

    def list_filtered(
        self,
        type_: RecommendationType | None,
        priority: str | None,
        skill: str | None,
    ) -> list[LearningRecommendation]:
        self._seed_if_empty()
        out: list[LearningRecommendation] = []
        for rec in self._recommendations.values():
            if rec.id in self._dismissed:
                continue
            if type_ is not None and rec.type != type_:
                continue
            if priority is not None and rec.priority != priority:
                continue
            if skill is not None and skill.lower() not in rec.skill.lower():
                continue
            out.append(rec)
        return out

    def dismiss(self, recommendation_id: str) -> DismissResponse:
        self._seed_if_empty()
        if recommendation_id not in self._recommendations:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        self._dismissed.add(recommendation_id)
        return DismissResponse(recommendation_id=recommendation_id, dismissed=True)

    def mark_opened(self, recommendation_id: str) -> MarkOpenedResponse:
        self._seed_if_empty()
        if recommendation_id not in self._recommendations:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        self._opened.add(recommendation_id)
        return MarkOpenedResponse(recommendation_id=recommendation_id, opened=True)

    def apply_temp_demo_seed(self) -> None:
        self._seed_if_empty()
        now = datetime.now(timezone.utc)
        if "rec_demo_api" not in self._recommendations:
            self._recommendations["rec_demo_api"] = LearningRecommendation(
                id="rec_demo_api",
                type=RecommendationType.skill_based,
                title="REST API design checklist",
                skill="api-design",
                reason="Covers idempotency and error shapes used in contributor endpoints.",
                difficulty="beginner",
                estimated_hours=0.75,
                resource_url="https://example.com/learn/rest-checklist",
                related_task_id=None,
                priority="low",
                recommended_at=now,
            )
        if "rec_e2e_task" not in self._recommendations:
            self._recommendations["rec_e2e_task"] = LearningRecommendation(
                id="rec_e2e_task",
                type=RecommendationType.task_based,
                title="Finish workroom checklist on tsk_002",
                skill="React",
                reason="Matches your in-progress funnel chart task and unblocks submission.",
                difficulty="intermediate",
                estimated_hours=2.0,
                resource_url="https://example.com/learn/d3-funnel",
                related_task_id="tsk_002",
                priority="urgent",
                recommended_at=now,
            )


store = LearningStore()


def apply_temp_demo_seed() -> None:
    store.apply_temp_demo_seed()

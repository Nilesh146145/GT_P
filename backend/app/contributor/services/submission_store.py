"""In-memory submission store. Replace with database persistence."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Annotated, Any

from fastapi import Depends

from app.contributor.dependencies import get_contributor_id
from app.contributor.schemas.submissions import (
    ChecklistAcknowledgement,
    EvidenceItemInput,
    EvidenceItemOut,
    RubricScore,
    SubmissionFileRef,
    SubmissionStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SubmissionRecord:
    id: str
    task_id: str
    version: int
    submitted_at: datetime | None
    status: SubmissionStatus
    notes: str | None
    file_ids: list[str]
    evidence: list[EvidenceItemOut]
    structured_responses: list[dict[str, Any]]
    checklist_acknowledgements: list[ChecklistAcknowledgement] = field(
        default_factory=list
    )
    review_score: float | None = None
    reviewer_feedback: str | None = None
    rubric_scores: list[RubricScore] = field(default_factory=list)


class SubmissionStore:
    def __init__(self) -> None:
        self._subs: dict[str, SubmissionRecord] = {}

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    def get(self, submission_id: str) -> SubmissionRecord | None:
        return self._subs.get(submission_id)

    def list_filtered(
        self,
        *,
        status: SubmissionStatus | None,
        task_id: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[SubmissionRecord], int]:
        rows = list(self._subs.values())
        if status is not None:
            rows = [r for r in rows if r.status == status]
        if task_id is not None:
            rows = [r for r in rows if r.task_id == task_id]
        rows.sort(key=lambda r: r.id)
        total = len(rows)
        start = (page - 1) * page_size
        return rows[start : start + page_size], total

    def create_for_task(
        self,
        task_id: str,
        *,
        version: int | None,
        notes: str | None,
        file_ids: list[str],
        evidence_items: list[EvidenceItemInput],
        structured_responses: list[dict[str, Any]],
        as_draft: bool,
    ) -> SubmissionRecord:
        existing = [r for r in self._subs.values() if r.task_id == task_id]
        next_v = max((r.version for r in existing), default=0) + 1
        vid = version if version is not None else next_v
        now = _utcnow()
        ev = [
            EvidenceItemOut(
                label=e.label,
                description=e.description,
                file_id=e.file_id,
                url=e.url,
                checklist_item_id=e.checklist_item_id,
            )
            for e in evidence_items
        ]
        rec = SubmissionRecord(
            id=self._new_id(),
            task_id=task_id,
            version=vid,
            submitted_at=None if as_draft else now,
            status=SubmissionStatus.draft if as_draft else SubmissionStatus.submitted,
            notes=notes,
            file_ids=list(file_ids),
            evidence=ev,
            structured_responses=list(structured_responses),
            checklist_acknowledgements=[],
        )
        self._subs[rec.id] = rec
        return rec

    def is_editable(self, rec: SubmissionRecord) -> bool:
        """ASN-002: no edits after submit unless rework (needs_revision)."""
        return rec.status in (
            SubmissionStatus.draft,
            SubmissionStatus.needs_revision,
        )

    def update(
        self,
        submission_id: str,
        *,
        version: int | None = None,
        notes: str | None = None,
        file_ids: list[str] | None = None,
        evidence_items: list[EvidenceItemInput] | None = None,
        structured_responses: list[dict[str, Any]] | None = None,
        checklist_acknowledgements: list[ChecklistAcknowledgement] | None = None,
    ) -> SubmissionRecord | None:
        rec = self._subs.get(submission_id)
        if rec is None:
            return None
        if version is not None:
            rec.version = version
        if notes is not None:
            rec.notes = notes
        if file_ids is not None:
            rec.file_ids = list(file_ids)
        if evidence_items is not None:
            rec.evidence = [
                EvidenceItemOut(
                    label=e.label,
                    description=e.description,
                    file_id=e.file_id,
                    url=e.url,
                    checklist_item_id=e.checklist_item_id,
                )
                for e in evidence_items
            ]
        if structured_responses is not None:
            rec.structured_responses = list(structured_responses)
        if checklist_acknowledgements is not None:
            by_id = {c.criterion_id: c for c in rec.checklist_acknowledgements}
            for item in checklist_acknowledgements:
                by_id[item.criterion_id] = item
            rec.checklist_acknowledgements = list(by_id.values())
        return rec

    def submit(
        self,
        submission_id: str,
        *,
        notes: str | None,
        confirm_checklist_complete: bool,
    ) -> SubmissionRecord | None:
        rec = self._subs.get(submission_id)
        if rec is None:
            return None
        if notes is not None:
            rec.notes = notes
        rec.submitted_at = _utcnow()
        rec.status = SubmissionStatus.submitted
        _ = confirm_checklist_complete
        return rec

    def resubmit(
        self,
        submission_id: str,
        *,
        notes: str | None,
        file_ids: list[str],
        evidence_items: list[EvidenceItemInput],
    ) -> SubmissionRecord | None:
        rec = self._subs.get(submission_id)
        if rec is None:
            return None
        if notes is not None:
            rec.notes = notes
        rec.file_ids = list(file_ids)
        rec.evidence = [
            EvidenceItemOut(
                label=e.label,
                description=e.description,
                file_id=e.file_id,
                url=e.url,
                checklist_item_id=e.checklist_item_id,
            )
            for e in evidence_items
        ]
        rec.submitted_at = _utcnow()
        rec.status = SubmissionStatus.submitted
        rec.version = rec.version + 1
        return rec

    def latest_for_task(self, task_id: str) -> SubmissionRecord | None:
        rows = [r for r in self._subs.values() if r.task_id == task_id]
        if not rows:
            return None
        return max(
            rows,
            key=lambda r: (
                r.version,
                r.submitted_at.timestamp() if r.submitted_at else 0.0,
            ),
        )


store = SubmissionStore()

_submission_stores: dict[str, SubmissionStore] = {}
_submission_stores_lock = RLock()


def get_submission_store(
    contributor_id: Annotated[str, Depends(get_contributor_id)],
) -> SubmissionStore:
    """Isolated in-memory submissions per authenticated contributor."""
    with _submission_stores_lock:
        s = _submission_stores.get(contributor_id)
        if s is None:
            s = SubmissionStore()
            _submission_stores[contributor_id] = s
            apply_temp_demo_seed_to(s)
        return s


def file_refs_for_ids(file_ids: list[str]) -> list[SubmissionFileRef]:
    return [SubmissionFileRef(id=fid, filename=None, mime_type=None) for fid in file_ids]


def apply_temp_demo_seed_to(target: SubmissionStore) -> None:
    """Fixed demo submissions aligned with seeded task ids (tsk_001 … tsk_005)."""
    s = target._subs
    if "sub_demo_draft" in s:
        return
    now = _utcnow()
    s["sub_demo_draft"] = SubmissionRecord(
        id="sub_demo_draft",
        task_id="tsk_001",
        version=1,
        submitted_at=None,
        status=SubmissionStatus.draft,
        notes="Draft for OAuth task",
        file_ids=["file_demo_1"],
        evidence=[
            EvidenceItemOut(label="screenshot", description=None, file_id=None, url="https://example.com/preview", checklist_item_id=None)
        ],
        structured_responses=[{"q": "env", "a": "staging"}],
        checklist_acknowledgements=[],
    )
    s["sub_demo_submitted"] = SubmissionRecord(
        id="sub_demo_submitted",
        task_id="tsk_003",
        version=1,
        submitted_at=now,
        status=SubmissionStatus.submitted,
        notes="Integration tests attached",
        file_ids=["file_demo_2"],
        evidence=[],
        structured_responses=[],
        checklist_acknowledgements=[],
        review_score=None,
        reviewer_feedback=None,
        rubric_scores=[],
    )
    s["sub_demo_rework"] = SubmissionRecord(
        id="sub_demo_rework",
        task_id="tsk_005",
        version=2,
        submitted_at=now,
        status=SubmissionStatus.needs_revision,
        notes="Address SQL edge cases",
        file_ids=[],
        evidence=[],
        structured_responses=[],
        checklist_acknowledgements=[],
        review_score=3.5,
        reviewer_feedback="Please add null handling for empty partitions.",
        rubric_scores=[RubricScore(criterion_id="correctness", score=3.5, max_score=5.0, comment="Edge cases")],
    )
    s["sub_demo_accepted"] = SubmissionRecord(
        id="sub_demo_accepted",
        task_id="tsk_004",
        version=1,
        submitted_at=now,
        status=SubmissionStatus.accepted,
        notes="Design audit accepted",
        file_ids=["file_design_pdf"],
        evidence=[],
        structured_responses=[],
        checklist_acknowledgements=[],
        review_score=4.9,
        reviewer_feedback="Excellent coverage of tokens and components.",
        rubric_scores=[
            RubricScore(criterion_id="completeness", score=5.0, max_score=5.0, comment=None),
        ],
    )


def apply_temp_demo_seed() -> None:
    """Seed the legacy module-level store (tests / one-off scripts)."""
    apply_temp_demo_seed_to(store)

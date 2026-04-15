from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from app.contributor.schemas.digital_twin import DigitalTwinHistoryResponse, DigitalTwinResponse, PeriodQuery
from app.contributor.schemas.evidence import EvidenceResponse, EvidenceSkillRef
from app.contributor.schemas.profile import ProfileResponse, SkillItem


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContributorStore:
    """In-memory store; swap for a database implementation."""

    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, Any]] = {}
        self._evidence: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self._digital_twin: dict[str, dict[str, Any]] = {}
        self._twin_history: dict[str, dict[str, list[dict[str, Any]]]] = {}

    def _ensure_profile(self, contributor_id: str) -> dict[str, Any]:
        if contributor_id not in self._profiles:
            self._profiles[contributor_id] = {
                "display_name": "Contributor",
                "anonymous_id": f"anon_{contributor_id[:8]}",
                "avatar": None,
                "email": f"{contributor_id}@example.local",
                "phone": None,
                "track": None,
                "verification_status": "unverified",
                "joined_at": _utcnow(),
                "profile_completeness": 0.42,
                "timezone": "UTC",
                "weekly_hours": 20,
                "availability": "weekdays",
                "language": "en",
                "bio": None,
                "country": None,
                "city": None,
                "skills": [],
            }
        return self._profiles[contributor_id]

    def get_profile(self, contributor_id: str) -> ProfileResponse:
        p = copy.deepcopy(self._ensure_profile(contributor_id))
        skills_raw = p.pop("skills", []) or []
        skills = [SkillItem(**s) if isinstance(s, dict) else s for s in skills_raw]
        return ProfileResponse(**p, skills=skills)

    def patch_profile(self, contributor_id: str, data: dict[str, Any]) -> ProfileResponse:
        p = self._ensure_profile(contributor_id)
        for k, v in data.items():
            if v is not None and k in {
                "display_name",
                "bio",
                "phone",
                "country",
                "city",
                "timezone",
                "weekly_hours",
                "availability",
                "language",
            }:
                p[k] = v
        return self.get_profile(contributor_id)

    def put_skills(self, contributor_id: str, skills: list[SkillItem]) -> ProfileResponse:
        p = self._ensure_profile(contributor_id)
        p["skills"] = [s.model_dump() for s in skills]
        return self.get_profile(contributor_id)

    def list_evidence(
        self,
        contributor_id: str,
        q: str | None = None,
        type_filter: str | None = None,
        skill: str | None = None,
    ) -> tuple[list[EvidenceResponse], int]:
        items = self._evidence.get(contributor_id, {}).get("items", [])
        out: list[dict[str, Any]] = []
        for row in items:
            if type_filter and row.get("type") != type_filter:
                continue
            if skill:
                sks = row.get("skills") or []
                if not any(
                    (isinstance(s, dict) and s.get("name", "").lower() == skill.lower())
                    or (getattr(s, "name", "") or "").lower() == skill.lower()
                    for s in sks
                ):
                    continue
            if q:
                ql = q.lower()
                if ql not in (row.get("title") or "").lower() and ql not in (
                    row.get("description") or ""
                ).lower():
                    continue
            out.append(row)
        responses = [
            EvidenceResponse(
                id=r["id"],
                title=r["title"],
                type=r["type"],
                url=r.get("url"),
                file_id=r.get("file_id"),
                description=r.get("description"),
                skills=[
                    EvidenceSkillRef.model_validate(x) if not isinstance(x, EvidenceSkillRef) else x
                    for x in (r.get("skills") or [])
                ],
            )
            for r in out
        ]
        return responses, len(responses)

    def create_evidence(self, contributor_id: str, payload: dict[str, Any]) -> EvidenceResponse:
        if contributor_id not in self._evidence:
            self._evidence[contributor_id] = {"items": []}
        eid = str(uuid.uuid4())
        row = {
            "id": eid,
            "title": payload["title"],
            "type": payload["type"],
            "url": payload.get("url"),
            "file_id": payload.get("file_id"),
            "description": payload.get("description"),
            "skills": [s if isinstance(s, dict) else s.model_dump() for s in payload.get("skills", [])],
        }
        self._evidence[contributor_id]["items"].append(row)
        return EvidenceResponse(
            id=eid,
            title=row["title"],
            type=row["type"],
            url=row.get("url"),
            file_id=row.get("file_id"),
            description=row.get("description"),
            skills=[EvidenceSkillRef.model_validate(x) for x in row["skills"]],
        )

    def get_evidence_row(self, contributor_id: str, evidence_id: str) -> dict[str, Any] | None:
        for row in self._evidence.get(contributor_id, {}).get("items", []):
            if row.get("id") == evidence_id:
                return row
        return None

    def update_evidence(
        self, contributor_id: str, evidence_id: str, patch: dict[str, Any]
    ) -> EvidenceResponse | None:
        row = self.get_evidence_row(contributor_id, evidence_id)
        if not row:
            return None
        for k in ("title", "type", "url", "file_id", "description"):
            if k in patch and patch[k] is not None:
                row[k] = patch[k]
        if patch.get("skills") is not None:
            row["skills"] = [
                s if isinstance(s, dict) else s.model_dump() for s in patch["skills"]
            ]
        return EvidenceResponse(
            id=row["id"],
            title=row["title"],
            type=row["type"],
            url=row.get("url"),
            file_id=row.get("file_id"),
            description=row.get("description"),
            skills=[
                EvidenceSkillRef.model_validate(x) if not isinstance(x, EvidenceSkillRef) else x
                for x in (row.get("skills") or [])
            ],
        )

    def delete_evidence(self, contributor_id: str, evidence_id: str) -> bool:
        bucket = self._evidence.get(contributor_id, {}).get("items", [])
        for i, row in enumerate(bucket):
            if row.get("id") == evidence_id:
                bucket.pop(i)
                return True
        return False

    def get_digital_twin(self, contributor_id: str) -> DigitalTwinResponse:
        if contributor_id not in self._digital_twin:
            self._digital_twin[contributor_id] = {
                "updated_at": _utcnow(),
                "tasks_completed": 120,
                "total_submissions": 140,
                "acceptance_rate": 0.86,
                "on_time_delivery": 0.91,
                "sla_compliance": 0.88,
                "average_review_score": 4.2,
                "total_hours_logged": 340.5,
                "average_hours_per_task": 2.8,
                "skill_growth_rate": 0.12,
                "rework_rate": 0.07,
                "streak_days": 14,
                "longest_streak": 45,
                "top_skills": [{"name": "Python", "score": 0.92}, {"name": "Data labeling", "score": 0.85}],
                "monthly_activity": [
                    {"month": "2026-01", "tasks": 10, "hours": 28.0},
                    {"month": "2026-02", "tasks": 14, "hours": 35.0},
                ],
                "ai_insights": [
                    "Strong consistency on review feedback.",
                    "Consider taking more varied task types to broaden skills.",
                ],
            }
        d = copy.deepcopy(self._digital_twin[contributor_id])
        return DigitalTwinResponse.model_validate(d)

    def get_digital_twin_history(
        self, contributor_id: str, period: PeriodQuery
    ) -> DigitalTwinHistoryResponse:
        if contributor_id not in self._twin_history:
            self._twin_history[contributor_id] = {}
        key = period
        if key not in self._twin_history[contributor_id]:
            # Placeholder time-series for demo
            self._twin_history[contributor_id][key] = [
                {"at": "2026-01-01", "acceptance_rate": 0.82, "hours": 28.0},
                {"at": "2026-02-01", "acceptance_rate": 0.86, "hours": 35.0},
                {"at": "2026-03-01", "acceptance_rate": 0.88, "hours": 32.0},
            ]
        return DigitalTwinHistoryResponse(period=period, snapshots=self._twin_history[contributor_id][key])


store = ContributorStore()


def apply_temp_demo_seed() -> None:
    """Rich default contributor + evidence variants for E2E (filters, PATCH, DELETE)."""
    cid = "default"
    p = store._ensure_profile(cid)
    p.update(
        {
            "display_name": "Jordan Rivera",
            "bio": "E2E demo contributor — multimodal labeling track; use X-Contributor-Id: default.",
            "track": "multimodal_labeling",
            "verification_status": "verified",
            "profile_completeness": 0.82,
            "timezone": "Europe/London",
            "weekly_hours": 32,
            "availability": "32h/week",
            "country": "GB",
            "city": "London",
            "phone": "+44-20-5555-0100",
            "skills": [
                {"name": "Python", "proficiency": "advanced"},
                {"name": "Image annotation", "proficiency": "expert"},
                {"name": "Audio transcription", "proficiency": "intermediate"},
            ],
        }
    )
    bucket = store._evidence.setdefault(cid, {}).setdefault("items", [])
    have = {row["id"] for row in bucket}
    seed_rows: list[dict[str, Any]] = [
        {
            "id": "ev_demo_link",
            "title": "Kaggle notebook — baseline model",
            "type": "link",
            "url": "https://example.com/evidence/notebook",
            "file_id": None,
            "description": "Public notebook used as skill evidence",
            "skills": [{"name": "Python", "proficiency": None}],
        },
        {
            "id": "ev_demo_github",
            "title": "OSS PR — labeling utilities",
            "type": "github",
            "url": "https://github.com/example/glimmora-utils/pull/42",
            "file_id": None,
            "description": "Merged PR referenced as evidence",
            "skills": [{"name": "Python", "proficiency": None}],
        },
        {
            "id": "ev_demo_file",
            "title": "Signed competency PDF",
            "type": "file",
            "url": None,
            "file_id": "file_competency_2026",
            "description": "Uploaded certificate scan",
            "skills": [{"name": "Image annotation", "proficiency": None}],
        },
    ]
    for row in seed_rows:
        if row["id"] not in have:
            bucket.append(row)

    if cid not in store._twin_history:
        store._twin_history[cid] = {}
    store._twin_history[cid]["6m"] = [
        {"at": "2025-11-01", "acceptance_rate": 0.80, "hours": 30.0},
        {"at": "2025-12-01", "acceptance_rate": 0.84, "hours": 38.0},
        {"at": "2026-01-01", "acceptance_rate": 0.86, "hours": 28.0},
        {"at": "2026-02-01", "acceptance_rate": 0.87, "hours": 35.0},
        {"at": "2026-03-01", "acceptance_rate": 0.88, "hours": 32.0},
    ]
    store._twin_history[cid]["1y"] = [
        {"at": "2025-Q2", "acceptance_rate": 0.78, "hours": 120.0},
        {"at": "2025-Q3", "acceptance_rate": 0.82, "hours": 140.0},
        {"at": "2025-Q4", "acceptance_rate": 0.85, "hours": 135.0},
        {"at": "2026-Q1", "acceptance_rate": 0.88, "hours": 150.0},
    ]

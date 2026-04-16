"""Rich demo seed for all contributor task API scenarios."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.contributor.db.persistence import FullState, get_db_path, load_state, save_state
from app.contributor.schemas.tasks import (
    DataSensitivity,
    PricingModel,
    Seniority,
    TaskPriority,
    TaskStatus,
    UploadCategory,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_seed_state() -> FullState:
    now = _utcnow()
    anchor = now.date()

    # Same ISO week deadlines for concurrent-deadline notice (accept-impact)
    d_w1 = anchor + timedelta(days=2)
    d_w2 = anchor + timedelta(days=3)
    d_w3 = anchor + timedelta(days=4)

    def task(
        tid: str,
        *,
        title: str,
        status: TaskStatus,
        priority: TaskPriority,
        hours: float,
        amount: float,
        model: PricingModel,
        due: date,
        skills: list[str],
        domain: str,
        sen: Seniority,
        sensitivity: DataSensitivity,
        nda: bool,
        offer_exp: datetime | None,
        offered: datetime | None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "id": tid,
            "project_id": f"prj_{tid[-3:]}",
            "project_title": f"Project {tid}",
            "milestone_title": f"Milestone for {title[:24]}",
            "title": title,
            "description": f"Full description for {title}. Deliver quality work per acceptance criteria.",
            "status": status,
            "priority": priority,
            "skills_required": skills,
            "estimated_hours": hours,
            "pricing": {"amount": amount, "currency": "USD", "model": model},
            "match_score": 0.55 + (hash(tid) % 40) / 100.0,
            "match_reason": "Seeded match for API testing",
            "due_date": due,
            "sla_deadline": datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1),
            "assigned_at": now - timedelta(days=4) if status != TaskStatus.available else None,
            "started_at": now - timedelta(days=1) if status == TaskStatus.in_progress else None,
            "submitted_at": now - timedelta(hours=6) if status == TaskStatus.submitted else None,
            "accepted_at": now - timedelta(days=3) if status in (TaskStatus.in_progress, TaskStatus.submitted, TaskStatus.completed, TaskStatus.rework) else None,
            "review_score": 4.7 if status == TaskStatus.completed else None,
            "review_comment": "Great work." if status == TaskStatus.completed else None,
            "rework_reason": "Please address review comments on error handling." if status == TaskStatus.rework else None,
            "rework_deadline": now + timedelta(days=3) if status == TaskStatus.rework else None,
            "progress_percent": {"available": 0.0, "in_progress": 40.0, "submitted": 100.0, "completed": 100.0, "rework": 55.0}[status.value],
            "hours_logged": hours * 0.3 if status != TaskStatus.available else 0.0,
            "domain_tag": domain,
            "seniority_required": sen,
            "offer_expires_at": offer_exp,
            "offered_at": offered,
            "data_sensitivity": sensitivity,
            "nda_required": nda,
            "acceptance_criteria": [
                f"Criterion 1 for {tid}: meet functional spec.",
                f"Criterion 2 for {tid}: include tests or evidence as listed.",
            ],
            "evidence_types_required": ["code_files", "document", "test_report"],
            "milestone_number": int(tid.split("_")[-1]) % 5 + 1,
            "reference_materials": [
                {"id": f"ref_{tid}", "name": f"Style guide — {domain}", "url": "https://example.com/ref", "description": "Enterprise reference"},
            ],
            "reviewer_guidance_preview": "Focus on accessibility first." if tid.endswith("001") else None,
        }
        if extra:
            row.update(extra)
        return row

    tasks: dict[str, dict[str, Any]] = {
        "tsk_001": task(
            "tsk_001",
            title="Implement OAuth callback",
            status=TaskStatus.available,
            priority=TaskPriority.high,
            hours=8.0,
            amount=400.0,
            model=PricingModel.fixed,
            due=d_w1,
            skills=["Python", "OAuth"],
            domain="Finance",
            sen=Seniority.mid,
            sensitivity=DataSensitivity.confidential,
            nda=True,
            offer_exp=now + timedelta(hours=48),
            offered=now - timedelta(hours=8),
        ),
        "tsk_002": task(
            "tsk_002",
            title="Build funnel chart",
            status=TaskStatus.in_progress,
            priority=TaskPriority.medium,
            hours=12.0,
            amount=720.0,
            model=PricingModel.hourly,
            due=d_w2,
            skills=["React", "D3"],
            domain="E-Commerce",
            sen=Seniority.junior,
            sensitivity=DataSensitivity.internal,
            nda=False,
            offer_exp=None,
            offered=now - timedelta(days=2),
        ),
        "tsk_003": task(
            "tsk_003",
            title="Write API integration tests",
            status=TaskStatus.submitted,
            priority=TaskPriority.low,
            hours=6.0,
            amount=300.0,
            model=PricingModel.fixed,
            due=anchor + timedelta(days=21),
            skills=["Python", "pytest"],
            domain="Education",
            sen=Seniority.fresher,
            sensitivity=DataSensitivity.public,
            nda=False,
            offer_exp=None,
            offered=now - timedelta(days=10),
        ),
        "tsk_004": task(
            "tsk_004",
            title="Design system audit",
            status=TaskStatus.completed,
            priority=TaskPriority.medium,
            hours=10.0,
            amount=950.0,
            model=PricingModel.milestone,
            due=anchor - timedelta(days=2),
            skills=["Figma", "Design"],
            domain="Healthcare",
            sen=Seniority.senior,
            sensitivity=DataSensitivity.internal,
            nda=False,
            offer_exp=None,
            offered=now - timedelta(days=30),
        ),
        "tsk_005": task(
            "tsk_005",
            title="ETL pipeline hardening",
            status=TaskStatus.rework,
            priority=TaskPriority.urgent,
            hours=20.0,
            amount=1200.0,
            model=PricingModel.hourly,
            due=anchor + timedelta(days=5),
            skills=["Python", "SQL"],
            domain="Finance",
            sen=Seniority.lead,
            sensitivity=DataSensitivity.restricted,
            nda=True,
            offer_exp=None,
            offered=now - timedelta(days=7),
        ),
        "tsk_006": task(
            "tsk_006",
            title="Large migration script (over-cap test)",
            status=TaskStatus.available,
            priority=TaskPriority.high,
            hours=30.0,
            amount=2400.0,
            model=PricingModel.fixed,
            due=anchor + timedelta(days=14),
            skills=["Python", "SQL"],
            domain="Finance",
            sen=Seniority.senior,
            sensitivity=DataSensitivity.confidential,
            nda=True,
            offer_exp=now + timedelta(days=5),
            offered=now - timedelta(days=1),
        ),
        "tsk_007": task(
            "tsk_007",
            title="Expired offer task",
            status=TaskStatus.available,
            priority=TaskPriority.low,
            hours=4.0,
            amount=120.0,
            model=PricingModel.fixed,
            due=anchor + timedelta(days=10),
            skills=["Rust"],
            domain="Education",
            sen=Seniority.junior,
            sensitivity=DataSensitivity.public,
            nda=False,
            offer_exp=now - timedelta(hours=2),
            offered=now - timedelta(days=1),
        ),
        "tsk_008": task(
            "tsk_008",
            title="Medium effort analytics widget",
            status=TaskStatus.available,
            priority=TaskPriority.medium,
            hours=16.0,
            amount=880.0,
            model=PricingModel.hourly,
            due=anchor + timedelta(days=5),
            skills=["TypeScript", "React"],
            domain="E-Commerce",
            sen=Seniority.mid,
            sensitivity=DataSensitivity.public,
            nda=False,
            offer_exp=now + timedelta(days=3),
            offered=now - timedelta(hours=12),
        ),
        "tsk_009": task(
            "tsk_009",
            title="Enterprise data lake documentation",
            status=TaskStatus.available,
            priority=TaskPriority.high,
            hours=40.0,
            amount=3200.0,
            model=PricingModel.milestone,
            due=anchor + timedelta(days=28),
            skills=["Technical Writing", "AWS"],
            domain="Healthcare",
            sen=Seniority.lead,
            sensitivity=DataSensitivity.restricted,
            nda=True,
            offer_exp=now + timedelta(days=6),
            offered=now - timedelta(days=2),
        ),
        "tsk_010": task(
            "tsk_010",
            title="Concurrent deadline peer A",
            status=TaskStatus.in_progress,
            priority=TaskPriority.medium,
            hours=8.0,
            amount=400.0,
            model=PricingModel.fixed,
            due=d_w3,
            skills=["Go"],
            domain="Finance",
            sen=Seniority.mid,
            sensitivity=DataSensitivity.internal,
            nda=False,
            offer_exp=None,
            offered=now - timedelta(days=4),
        ),
        "tsk_011": task(
            "tsk_011",
            title="Concurrent deadline peer B",
            status=TaskStatus.in_progress,
            priority=TaskPriority.medium,
            hours=6.0,
            amount=360.0,
            model=PricingModel.fixed,
            due=d_w2,
            skills=["Kubernetes"],
            domain="Finance",
            sen=Seniority.mid,
            sensitivity=DataSensitivity.internal,
            nda=False,
            offer_exp=None,
            offered=now - timedelta(days=4),
        ),
        "tsk_012": task(
            "tsk_012",
            title="Concurrent deadline peer C (still offered)",
            status=TaskStatus.available,
            priority=TaskPriority.low,
            hours=5.0,
            amount=250.0,
            model=PricingModel.fixed,
            due=d_w3,
            skills=["Docker"],
            domain="Finance",
            sen=Seniority.junior,
            sensitivity=DataSensitivity.public,
            nda=False,
            offer_exp=now + timedelta(days=2),
            offered=now - timedelta(hours=5),
        ),
    }

    def wr(
        tid: str,
        *,
        instructions: str,
        templates: list[dict],
        links: list[dict],
        uploads: list[dict],
        qa: list[dict],
        checklist: list[dict],
        last_act: datetime,
    ) -> dict[str, Any]:
        return {
            "instructions": instructions,
            "templates": templates,
            "links": links,
            "uploads": uploads,
            "qa_messages": qa,
            "evidence_checklist": checklist,
            "last_activity_at": last_act,
        }

    workroom: dict[str, dict[str, Any]] = {
        "tsk_001": wr(
            "tsk_001",
            instructions="Follow OAuth spec; use workroom templates before PR.",
            templates=[{"id": "tpl_1", "name": "PR template", "url": None, "description": "Use for final PR"}],
            links=[{"id": "lnk_1", "title": "RFC 6749", "url": "https://datatracker.ietf.org/doc/html/rfc6749", "description": None}],
            uploads=[],
            qa=[],
            checklist=[
                {"id": "chk_1", "label": "Unit tests pass", "completed": False, "evidence_file_id": None, "notes": None},
                {"id": "chk_2", "label": "Security review notes addressed", "completed": False, "evidence_file_id": None, "notes": None},
            ],
            last_act=now,
        ),
        "tsk_002": wr(
            "tsk_002",
            instructions="Use design tokens from Figma.",
            templates=[],
            links=[{"id": "lnk_2", "title": "Figma", "url": "https://figma.com", "description": "Design"}],
            uploads=[
                {
                    "id": "upl_seed_1",
                    "filename": "draft.png",
                    "category": UploadCategory.draft,
                    "title": "First draft",
                    "description": None,
                    "uploaded_at": now - timedelta(hours=3),
                    "size_bytes": 2048,
                }
            ],
            qa=[
                {
                    "id": "qa_seed_1",
                    "author": "Reviewer",
                    "message": "Please align colors with brand palette.",
                    "created_at": now - timedelta(hours=2),
                    "attachment_ids": [],
                }
            ],
            checklist=[],
            last_act=now - timedelta(hours=1),
        ),
    }

    for tid in tasks:
        if tid not in workroom:
            workroom[tid] = wr(
                tid,
                instructions=f"Default workroom instructions for {tid}.",
                templates=[{"id": f"tpl_{tid}", "name": "Generic template", "url": "https://example.com/t", "description": None}],
                links=[{"id": f"lnk_{tid}", "title": "Docs", "url": "https://example.com/docs", "description": None}],
                uploads=[],
                qa=[],
                checklist=[
                    {"id": f"chk_{tid}_1", "label": "Deliverable attached", "completed": False, "evidence_file_id": None, "notes": None},
                ],
                last_act=now - timedelta(minutes=30),
            )

    timelines: dict[str, list[dict[str, Any]]] = {}
    for tid in tasks:
        timelines[tid] = [
            {
                "id": f"ev_{tid}_created",
                "event_type": "created",
                "at": now - timedelta(days=8),
                "label": "Task created",
                "metadata": {},
            },
        ]
    timelines["tsk_002"].append(
        {"id": "ev_assign", "event_type": "assigned", "at": now - timedelta(days=2), "label": "Assigned", "metadata": {}}
    )
    timelines["tsk_002"].append(
        {"id": "ev_start", "event_type": "started", "at": now - timedelta(days=1), "label": "Work started", "metadata": {}}
    )

    profile: dict[str, Any] = {
        "seniority": Seniority.mid,
        "skill_tags": {"python", "oauth", "typescript", "react", "pytest", "sql"},
        "declared_hours_per_week": 32.0,
        "hours_committed_this_week": 18.0,
    }

    return FullState(
        tasks=tasks,
        workroom=workroom,
        timelines=timelines,
        declined=[],
        profile=profile,
    )


def reset_database_to_seed(path: Path | None = None) -> Path:
    """Overwrite DB with fresh seed (for manual reset / tests)."""
    p = path or get_db_path()
    state = build_seed_state()
    save_state(state, p)
    return p


def ensure_seeded_database(path: Path | None = None) -> Path:
    """Create DB and seed if missing."""
    p = path or get_db_path()
    if load_state(p) is None:
        reset_database_to_seed(p)
    return p

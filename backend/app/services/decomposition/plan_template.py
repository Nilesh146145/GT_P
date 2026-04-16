"""Default decomposition graph for new plans (placeholder until AGI generation is wired)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_task_list() -> list[dict[str, Any]]:
    return [
        {
            "id": 1,
            "milestone": "M1",
            "task_name": "Design API",
            "skills": "Python",
            "seniority": "Senior",
            "effort": 5,
            "start_date": "2026-04-01",
            "end_date": "2026-04-05",
            "critical": True,
        },
        {
            "id": 2,
            "milestone": "M1",
            "task_name": "Build UI",
            "skills": "React",
            "seniority": "Junior",
            "effort": 3,
            "start_date": "2026-04-06",
            "end_date": "2026-04-08",
            "critical": False,
        },
        {
            "id": 3,
            "milestone": "M2",
            "task_name": "Integration testing",
            "skills": "SQL",
            "seniority": "Mid",
            "effort": 4,
            "start_date": "2026-04-09",
            "end_date": "2026-04-12",
            "critical": True,
        },
    ]


def default_task_details() -> list[dict[str, Any]]:
    return [
        {
            "id": 1,
            "task_id": "TSK-001-001",
            "task_name": "Design API",
            "milestone": "M1",
            "skills": ["Python", "FastAPI"],
            "seniority": "Senior",
            "effort_days": 5,
            "start_date": "2026-04-01",
            "end_date": "2026-04-05",
            "critical": True,
            "acceptance_criteria": "API should handle 1000 req/sec with documented OpenAPI spec.",
            "data_sensitivity": "High",
            "evidence_types": ["code", "test report"],
        },
        {
            "id": 2,
            "task_id": "TSK-001-002",
            "task_name": "Build UI",
            "milestone": "M1",
            "skills": ["React"],
            "seniority": "Junior",
            "effort_days": 3,
            "start_date": "2026-04-06",
            "end_date": "2026-04-08",
            "critical": False,
            "acceptance_criteria": "Responsive UI with API integration and accessibility checks.",
            "data_sensitivity": "Low",
            "evidence_types": ["design files"],
        },
        {
            "id": 3,
            "task_id": "TSK-002-001",
            "task_name": "Integration testing",
            "milestone": "M2",
            "skills": ["SQL", "pytest"],
            "seniority": "Mid",
            "effort_days": 4,
            "start_date": "2026-04-09",
            "end_date": "2026-04-12",
            "critical": True,
            "acceptance_criteria": "End-to-end tests green; test report attached.",
            "data_sensitivity": "Medium",
            "evidence_types": ["test report", "documentation"],
        },
    ]


def build_new_plan_document(
    *,
    plan_id: str,
    enterprise_profile_id: str,
    created_by_user_id: str,
    project_name: str,
    sow_reference: str,
    sow_version: str,
    sow_start: str | None,
    sow_end: str | None,
) -> dict[str, Any]:
    task_list = default_task_list()
    task_details = default_task_details()
    plan_start = min(t["start_date"] for t in task_list)
    plan_end = max(t["end_date"] for t in task_list)
    sow_s = sow_start or plan_start
    sow_e = sow_end or plan_end

    plan_content: dict[str, Any] = {
        "project_description": f"AI-generated task breakdown for {project_name}.",
        "plan_version": 1,
        "objective": "Deliver scope per agreed SOW milestones with clear acceptance criteria.",
        "scope": "Structured milestones, tasks, dependencies, and critical path derived from the SOW.",
        "total_duration_weeks": 4,
        "phases": [
            {
                "phase_number": 1,
                "phase_name": "Foundation",
                "duration_weeks": 2,
                "deliverables": ["API design", "UI shell"],
                "assigned_team": "Core build",
            },
            {
                "phase_number": 2,
                "phase_name": "Integration",
                "duration_weeks": 2,
                "deliverables": ["End-to-end flows"],
                "assigned_team": "Integration",
            },
        ],
        "risks": [
            {
                "risk_id": "R1",
                "description": "Dependency on client approvals",
                "severity": "medium",
                "mitigation": "Buffer milestones and early review gates",
            },
        ],
        "budget": {
            "total_estimated_cost": "TBD",
            "currency": "USD",
            "breakdown": {"engineering": "80%", "qa": "20%"},
        },
        "success_metrics": ["Milestones accepted per criteria", "Critical path maintained"],
        "assumptions": ["Client dependencies communicated in the SOW are honored"],
        "agi_confidence_score": 0.85,
        "generated_by": "AGI-decomposition-v1",
        "generated_at": _utc_iso(),
        "enterprise_deadline_to_confirm": "2026-05-01",
    }

    initial_snapshot = {
        "revision_index": 0,
        "notes": "Initial AGI plan",
        "tasks": deepcopy(task_list),
    }

    return {
        "plan_id": plan_id,
        "enterprise_profile_id": enterprise_profile_id,
        "created_by_user_id": created_by_user_id,
        "project_name": project_name,
        "sow_reference": sow_reference,
        "sow_version": sow_version,
        "kicked_off": False,
        "kicked_off_at": None,
        "withdrawn": False,
        "status": "PENDING_KICKOFF",
        "revision_requests_used": 0,
        "admin_notified_max_revision": False,
        "checklist": {"item1": False, "item2": False, "item3": False},
        "sow_start": sow_s,
        "sow_end": sow_e,
        "plan_start": plan_start,
        "plan_end": plan_end,
        "last_revision_notes": None,
        "revision_history": [],
        "flagged_task_ids": [],
        "plan_content": plan_content,
        "task_list": task_list,
        "task_details": task_details,
        "revision_snapshots": [initial_snapshot],
        "locked_at": None,
        "locked_by_contributor_id": None,
        "assignment_offer_id": None,
        "confirmed_at": None,
        "revision_requested_at": None,
    }

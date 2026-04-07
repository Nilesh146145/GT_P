from __future__ import annotations

from datetime import date

from fastapi import HTTPException

_TASKS_DB = [
    {"id": 1, "milestone": "M1", "effort": 5, "skills": ["Python"], "critical": True},
    {"id": 2, "milestone": "M1", "effort": 3, "skills": ["React"], "critical": False},
    {"id": 3, "milestone": "M2", "effort": 4, "skills": ["SQL"], "critical": True},
]

_PLAN_DATES = {
    1: {
        "sow_start": date(2026, 4, 1),
        "sow_end": date(2026, 4, 10),
        "plan_start": date(2026, 4, 1),
        "plan_end": date(2026, 4, 12),
    }
}


def get_summary_panel(plan_id: int) -> dict:
    if plan_id not in _PLAN_DATES:
        raise HTTPException(status_code=404, detail="Plan not found")

    milestones = {task["milestone"] for task in _TASKS_DB}
    total_tasks = len(_TASKS_DB)
    total_effort = sum(task["effort"] for task in _TASKS_DB)
    critical_tasks = [task for task in _TASKS_DB if task["critical"]]

    skills: set[str] = set()
    for task in _TASKS_DB:
        skills.update(task["skills"])

    dates = _PLAN_DATES[plan_id]
    diff = (dates["plan_end"] - dates["sow_end"]).days
    warning = f"Plan exceeds SOW by {diff} days" if diff > 0 else None

    return {
        "total_milestones": len(milestones),
        "total_tasks": total_tasks,
        "total_effort_days": total_effort,
        "critical_path_days": sum(task["effort"] for task in critical_tasks),
        "critical_tasks_count": len(critical_tasks),
        "skills": list(skills),
        "sow_start": dates["sow_start"],
        "sow_end": dates["sow_end"],
        "plan_start": dates["plan_start"],
        "plan_end": dates["plan_end"],
        "date_warning": warning,
    }


def get_plan_summary(plan_id: str):
    raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

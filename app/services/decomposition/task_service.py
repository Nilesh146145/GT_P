from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

_TASKS_DB = [
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
]

_TASK_DETAILS_DB = [
    {
        "id": 1,
        "task_id": "TSK-001-001",
        "task_name": "Design API",
        "milestone": "Backend",
        "skills": ["Python", "FastAPI"],
        "seniority": "Senior",
        "effort_days": 5,
        "start_date": "2026-04-01",
        "end_date": "2026-04-05",
        "critical": True,
        "acceptance_criteria": "API should handle 1000 req/sec",
        "data_sensitivity": "High",
        "evidence_types": ["code", "test report"],
    },
    {
        "id": 2,
        "task_id": "TSK-001-002",
        "task_name": "Build UI",
        "milestone": "Frontend",
        "skills": ["React"],
        "seniority": "Junior",
        "effort_days": 3,
        "start_date": "2026-04-06",
        "end_date": "2026-04-08",
        "critical": False,
        "acceptance_criteria": "Responsive UI with API integration",
        "data_sensitivity": "Low",
        "evidence_types": ["design files"],
    },
]

_FLAGGED_TASKS_DB = {1: []}


def get_tasks(plan_id: int) -> dict:
    return {"tasks": deepcopy(_TASKS_DB)}


def query_tasks(plan_id: int, milestone: str | None = None, sort_by: str | None = "id") -> dict:
    data = deepcopy(_TASKS_DB)
    if milestone:
        data = [task for task in data if task["milestone"] == milestone]

    try:
        data = sorted(data, key=lambda item: item.get(sort_by))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid sort field") from exc

    return {"tasks": data}


def get_task(plan_id: int, task_id: int) -> dict:
    for task in _TASKS_DB:
        if task["id"] == task_id:
            return deepcopy(task)
    raise HTTPException(status_code=404, detail="Task not found")


def get_milestones(plan_id: int) -> dict:
    result: dict[str, list[dict]] = {}
    for task in _TASKS_DB:
        result.setdefault(task["milestone"], []).append(deepcopy(task))
    return {"milestones": result}


def critical_tasks(plan_id: int) -> dict:
    return {"critical_tasks": [deepcopy(task) for task in _TASKS_DB if task["critical"]]}


def get_task_detail(plan_id: int, task_id: int) -> dict:
    for task in _TASK_DETAILS_DB:
        if task["id"] == task_id:
            return deepcopy(task)
    raise HTTPException(status_code=404, detail="Task not found")


def flag_task(plan_id: int, task_id: int) -> dict:
    task_exists = any(task["id"] == task_id for task in _TASK_DETAILS_DB)
    if not task_exists:
        raise HTTPException(status_code=404, detail="Task not found")

    _FLAGGED_TASKS_DB.setdefault(plan_id, [])
    if task_id not in _FLAGGED_TASKS_DB[plan_id]:
        _FLAGGED_TASKS_DB[plan_id].append(task_id)

    return {
        "message": "Task flagged for revision",
        "total_flagged": len(_FLAGGED_TASKS_DB[plan_id]),
        "flagged_tasks": deepcopy(_FLAGGED_TASKS_DB[plan_id]),
    }

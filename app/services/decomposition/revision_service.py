from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

from app.schemas.decomposition.revision import RevisionNotesRequest

_REVISION_DB = {
    1: {
        "revision_count": 0,
        "max_revisions": 3,
        "status": "PLAN REVIEW REQUIRED",
    }
}

_FLAGGED_TASKS_DB = {1: [1, 2]}
_TASKS_LOOKUP = {1: "Design API", 2: "Build UI", 3: "Testing"}

_REVISED_PLANS_DB = {
    1: [
        {
            "revision_id": 1,
            "tasks": [
                {"id": 1, "name": "Setup Project", "effort": 2},
                {"id": 2, "name": "Design DB", "effort": 3},
            ],
            "notes": "Initial plan",
        },
        {
            "revision_id": 2,
            "tasks": [
                {"id": 1, "name": "Setup Project", "effort": 3},
                {"id": 3, "name": "API Development", "effort": 5},
            ],
            "notes": "Updated effort and added API task",
        },
    ]
}


def get_plan_review_page(plan_id: str):
    raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")


def get_revision_modal(plan_id: int) -> dict:
    if plan_id not in _REVISION_DB:
        raise HTTPException(status_code=404, detail="Plan not found")

    revision_data = _REVISION_DB[plan_id]
    flagged_ids = _FLAGGED_TASKS_DB.get(plan_id, [])
    flagged_tasks = [{"id": task_id, "name": _TASKS_LOOKUP.get(task_id, "Unknown")} for task_id in flagged_ids]

    return {
        "revision_count": revision_data["revision_count"],
        "max_revisions": revision_data["max_revisions"],
        "status": revision_data["status"],
        "flagged_tasks": flagged_tasks,
    }


def request_revision(plan_id: int, data: RevisionNotesRequest) -> dict:
    if plan_id not in _REVISION_DB:
        raise HTTPException(status_code=404, detail="Plan not found")

    revision_data = _REVISION_DB[plan_id]
    if revision_data["revision_count"] >= revision_data["max_revisions"]:
        raise HTTPException(status_code=400, detail="Maximum revision limit reached")

    revision_data["revision_count"] += 1
    revision_data["status"] = "REVISION IN PROGRESS"
    _FLAGGED_TASKS_DB[plan_id] = []

    return {
        "message": "Revision request submitted",
        "revision_count": revision_data["revision_count"],
        "status": revision_data["status"],
    }


def calculate_diff(old_tasks: list[dict], new_tasks: list[dict]) -> tuple[list[int], list[int], list[int]]:
    old_map = {task["id"]: task for task in old_tasks}
    new_map = {task["id"]: task for task in new_tasks}

    added: list[int] = []
    modified: list[int] = []
    removed: list[int] = []

    for task_id, task in new_map.items():
        if task_id not in old_map:
            added.append(task_id)
        elif task != old_map[task_id]:
            modified.append(task_id)

    for task_id in old_map:
        if task_id not in new_map:
            removed.append(task_id)

    return added, modified, removed


def get_revised_plan(plan_id: int) -> dict:
    if plan_id not in _REVISED_PLANS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")

    versions = _REVISED_PLANS_DB[plan_id]
    if len(versions) < 2:
        raise HTTPException(status_code=400, detail="No revision available")

    latest = versions[-1]
    previous = versions[-2]
    added, modified, removed = calculate_diff(previous["tasks"], latest["tasks"])

    return {
        "current_revision": latest["revision_id"],
        "tasks": deepcopy(latest["tasks"]),
        "changes": {"added": added, "modified": modified, "removed": removed},
        "summary": {"added": len(added), "modified": len(modified), "removed": len(removed)},
    }


def get_revision_detail(plan_id: int, revision_id: int) -> dict:
    if plan_id not in _REVISED_PLANS_DB:
        raise HTTPException(status_code=404, detail="Plan not found")

    for version in _REVISED_PLANS_DB[plan_id]:
        if version["revision_id"] == revision_id:
            return {
                "revision_id": revision_id,
                "notes": version["notes"],
                "tasks": deepcopy(version["tasks"]),
            }

    raise HTTPException(status_code=404, detail="Revision not found")

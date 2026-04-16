"""Task graph endpoints for decomposition (plan-scoped, kick-off gated)."""

from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

from app.core.database import is_db_connected
from app.services.decomposition import plan_repository

_DCP005 = "This project has not been kicked off yet."


async def _tasks_context(enterprise_profile_id: str, plan_id: str) -> tuple[dict, list[dict], list[dict]]:
    if not is_db_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    doc = await plan_repository.find_by_plan_id(plan_id)
    if doc is None or doc.get("enterprise_profile_id") != enterprise_profile_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not doc.get("kicked_off") or doc.get("status") == "PENDING_KICKOFF":
        raise HTTPException(status_code=403, detail=_DCP005)
    tasks = list(doc.get("task_list") or [])
    details = list(doc.get("task_details") or [])
    return doc, tasks, details


def _flaggable(doc: dict) -> None:
    if doc.get("status") != "PLAN_REVIEW_REQUIRED":
        raise HTTPException(status_code=400, detail="Tasks can only be flagged during plan review (PLAN_REVIEW_REQUIRED).")


async def get_tasks(enterprise_profile_id: str, plan_id: str) -> dict:
    _, tasks, _ = await _tasks_context(enterprise_profile_id, plan_id)
    return {"tasks": deepcopy(tasks)}


async def query_tasks(
    enterprise_profile_id: str,
    plan_id: str,
    milestone: str | None = None,
    sort_by: str | None = "id",
) -> dict:
    _, tasks, _ = await _tasks_context(enterprise_profile_id, plan_id)
    data = deepcopy(tasks)
    if milestone:
        data = [task for task in data if task.get("milestone") == milestone]
    try:
        data = sorted(data, key=lambda item: item.get(sort_by))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid sort field") from exc
    return {"tasks": data}


async def get_task(enterprise_profile_id: str, plan_id: str, task_id: int) -> dict:
    _, tasks, _ = await _tasks_context(enterprise_profile_id, plan_id)
    for task in tasks:
        if int(task.get("id", -1)) == task_id:
            return deepcopy(task)
    raise HTTPException(status_code=404, detail="Task not found")


async def get_milestones(enterprise_profile_id: str, plan_id: str) -> dict:
    _, tasks, _ = await _tasks_context(enterprise_profile_id, plan_id)
    result: dict[str, list[dict]] = {}
    for task in tasks:
        m = str(task.get("milestone") or "")
        result.setdefault(m, []).append(deepcopy(task))
    return {"milestones": result}


async def critical_tasks(enterprise_profile_id: str, plan_id: str) -> dict:
    _, tasks, _ = await _tasks_context(enterprise_profile_id, plan_id)
    return {"critical_tasks": [deepcopy(task) for task in tasks if task.get("critical")]}


async def get_task_detail(enterprise_profile_id: str, plan_id: str, task_id: int) -> dict:
    _, _, details = await _tasks_context(enterprise_profile_id, plan_id)
    for task in details:
        if int(task.get("id", -1)) == task_id:
            return deepcopy(task)
    raise HTTPException(status_code=404, detail="Task not found")


async def flag_task(enterprise_profile_id: str, plan_id: str, task_id: int) -> dict:
    doc, _, details = await _tasks_context(enterprise_profile_id, plan_id)
    _flaggable(doc)
    if not any(int(t.get("id", -1)) == task_id for t in details):
        raise HTTPException(status_code=404, detail="Task not found")

    flagged = [int(x) for x in (doc.get("flagged_task_ids") or [])]
    if task_id not in flagged:
        flagged.append(task_id)
    await plan_repository.update_by_plan_id(plan_id, {"$set": {"flagged_task_ids": flagged}})
    return {
        "message": "Task flagged for revision",
        "plan_id": plan_id,
        "task_id": task_id,
        "flagged_count": len(flagged),
    }

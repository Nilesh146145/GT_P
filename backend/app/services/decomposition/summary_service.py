"""Summary panel / strip for Plan Review (§8.1.2)."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException

from app.core.database import is_db_connected
from app.services.decomposition import plan_repository

_DCP005 = "This project has not been kicked off yet."


async def _load(enterprise_profile_id: str, plan_id: str) -> dict:
    if not is_db_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    doc = await plan_repository.find_by_plan_id(plan_id)
    if doc is None or doc.get("enterprise_profile_id") != enterprise_profile_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not doc.get("kicked_off") or doc.get("status") == "PENDING_KICKOFF":
        raise HTTPException(status_code=403, detail=_DCP005)
    return doc


async def get_summary_panel(enterprise_profile_id: str, plan_id: str) -> dict:
    doc = await _load(enterprise_profile_id, plan_id)
    tasks = [t for t in (doc.get("task_list") or []) if isinstance(t, dict)]
    milestones = {t.get("milestone") for t in tasks}
    total_effort = sum(int(t.get("effort", 0) or 0) for t in tasks)
    critical_tasks = [t for t in tasks if t.get("critical")]
    crit_effort = sum(int(t.get("effort", 0) or 0) for t in critical_tasks)

    skills: set[str] = set()
    for task in tasks:
        s = task.get("skills")
        if isinstance(s, list):
            skills.update(str(x) for x in s)
        elif s:
            skills.add(str(s))

    try:
        sow_start = date.fromisoformat(str(doc.get("sow_start", ""))[:10])
        sow_end = date.fromisoformat(str(doc.get("sow_end", ""))[:10])
        plan_start = date.fromisoformat(str(doc.get("plan_start", ""))[:10])
        plan_end = date.fromisoformat(str(doc.get("plan_end", ""))[:10])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date fields on plan") from exc

    diff = (plan_end - sow_end).days
    warning = f"Plan end date exceeds SOW committed end date by {diff} days." if diff > 0 else None

    return {
        "total_milestones": len(milestones),
        "total_tasks": len(tasks),
        "total_effort_days": total_effort,
        "critical_path_days": crit_effort,
        "critical_tasks_count": len(critical_tasks),
        "skills": sorted(skills),
        "sow_start": sow_start,
        "sow_end": sow_end,
        "plan_start": plan_start,
        "plan_end": plan_end,
        "date_warning": warning,
    }


async def get_plan_summary(enterprise_profile_id: str, plan_id: str) -> dict:
    """Strip-style summary for Plan Review right panel."""
    doc = await _load(enterprise_profile_id, plan_id)
    panel = await get_summary_panel(enterprise_profile_id, plan_id)
    return {
        "plan_id": plan_id,
        "project_name": doc.get("project_name"),
        "status": doc.get("status"),
        "total_milestones": panel["total_milestones"],
        "total_tasks": panel["total_tasks"],
        "estimated_effort_days": panel["total_effort_days"],
        "project_start": doc.get("plan_start"),
        "project_end": doc.get("plan_end"),
        "critical_path_tasks": panel["critical_tasks_count"],
        "skills": panel["skills"],
        "sow_start": doc.get("sow_start"),
        "sow_end": doc.get("sow_end"),
        "plan_start": doc.get("plan_start"),
        "plan_end": doc.get("plan_end"),
        "date_warning": panel.get("date_warning"),
    }

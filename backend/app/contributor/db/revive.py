"""Convert JSON-loaded primitives back to Enums and datetimes."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.contributor.schemas.tasks import (
    DataSensitivity,
    PricingModel,
    Seniority,
    TaskPriority,
    TaskStatus,
    UploadCategory,
)


def _parse_dt(s: str) -> datetime:
    if s.endswith("Z"):
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def revive_task_row(t: dict[str, Any]) -> None:
    t["status"] = TaskStatus(t["status"])
    t["priority"] = TaskPriority(t["priority"])
    if t.get("pricing"):
        t["pricing"]["model"] = PricingModel(t["pricing"]["model"])
    if t.get("due_date") and isinstance(t["due_date"], str):
        t["due_date"] = date.fromisoformat(t["due_date"])
    for key in ("sla_deadline", "assigned_at", "started_at", "submitted_at", "accepted_at", "rework_deadline", "offer_expires_at", "offered_at"):
        if t.get(key) and isinstance(t[key], str):
            t[key] = _parse_dt(t[key])
    if t.get("seniority_required") and isinstance(t["seniority_required"], str):
        t["seniority_required"] = Seniority(t["seniority_required"])
    if t.get("data_sensitivity") and isinstance(t["data_sensitivity"], str):
        t["data_sensitivity"] = DataSensitivity(t["data_sensitivity"])


def revive_workroom(w: dict[str, Any]) -> None:
    if w.get("last_activity_at") and isinstance(w["last_activity_at"], str):
        w["last_activity_at"] = _parse_dt(w["last_activity_at"])
    for tpl in w.get("templates", []):
        pass
    for link in w.get("links", []):
        pass
    for u in w.get("uploads", []):
        if isinstance(u.get("category"), str):
            u["category"] = UploadCategory(u["category"])
        if u.get("uploaded_at") and isinstance(u["uploaded_at"], str):
            u["uploaded_at"] = _parse_dt(u["uploaded_at"])
    for m in w.get("qa_messages", []):
        if m.get("created_at") and isinstance(m["created_at"], str):
            m["created_at"] = _parse_dt(m["created_at"])
    for c in w.get("evidence_checklist", []):
        pass


def revive_timelines(timelines: dict[str, list[dict[str, Any]]]) -> None:
    for events in timelines.values():
        for e in events:
            if e.get("at") and isinstance(e["at"], str):
                e["at"] = _parse_dt(e["at"])


def revive_profile(p: dict[str, Any]) -> None:
    if p.get("seniority") and isinstance(p["seniority"], str):
        p["seniority"] = Seniority(p["seniority"])
    if p.get("skill_tags") and isinstance(p["skill_tags"], list):
        p["skill_tags"] = set(p["skill_tags"])


def revive_all(
    tasks: dict[str, dict[str, Any]],
    workroom: dict[str, dict[str, Any]],
    timelines: dict[str, list[dict[str, Any]]],
    profile: dict[str, Any],
) -> None:
    for t in tasks.values():
        revive_task_row(t)
    for w in workroom.values():
        revive_workroom(w)
    revive_timelines(timelines)
    revive_profile(profile)

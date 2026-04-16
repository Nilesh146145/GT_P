from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from threading import RLock
from typing import Annotated, Any

from fastapi import Depends

from app.contributor.db.persistence import FullState, get_db_path, load_state, save_state
from app.contributor.dependencies import get_contributor_id
from app.contributor.db.revive import revive_all
from app.contributor.db.seed import build_seed_state, ensure_seeded_database
from app.contributor.schemas.tasks import (
    AcceptBody,
    AcceptImpactResponse,
    ChecklistPatchBody,
    DeadlineWithinDiscovery,
    DeclineBody,
    DiscoverySummary,
    EffortFilter,
    EvidenceChecklistItem,
    PostWorkroomMessageBody,
    Pricing,
    QAMessage,
    ReferenceMaterial,
    RequestExtensionBody,
    Seniority,
    StartBody,
    TaskDetail,
    TaskListItem,
    TaskPriority,
    TaskSortBy,
    TaskStatus,
    TaskSummaryKPI,
    TimelineEvent,
    TimeFilter,
    UploadCategory,
    UploadResponse,
    WorkroomLink,
    WorkroomTemplate,
    WorkroomUpload,
    WorkroomView,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _effort_display(hours: float | None) -> str | None:
    if hours is None:
        return None
    if hours < 24:
        h = int(hours) if hours == int(hours) else hours
        return f"{h} hours"
    days = round(hours / 8.0, 1)
    return f"{days} days"


def _env_use_temp_db() -> bool:
    return os.environ.get("CONTRIBUTOR_TASKS_USE_DB", "true").strip().lower() in ("1", "true", "yes", "on")


class ContributorTaskService:
    def __init__(self, *, contributor_id: str, use_temp_db: bool | None = None) -> None:
        self._contributor_id = contributor_id
        self._db_path = get_db_path(contributor_id)
        self._use_temp_db = _env_use_temp_db() if use_temp_db is None else use_temp_db
        if self._use_temp_db:
            ensure_seeded_database(self._db_path)
            raw = load_state(self._db_path)
            if raw is None:
                st = build_seed_state()
                save_state(st, self._db_path)
                raw = load_state(self._db_path)
            assert raw is not None
            revive_all(raw.tasks, raw.workroom, raw.timelines, raw.profile)
            self._tasks = raw.tasks
            self._workroom = raw.workroom
            self._timelines = raw.timelines
            self._declined_task_ids = set(raw.declined)
            self._profile = raw.profile
        else:
            st = build_seed_state()
            self._tasks = st.tasks
            self._workroom = st.workroom
            self._timelines = st.timelines
            self._declined_task_ids = set(st.declined)
            self._profile = st.profile

    def _persist(self) -> None:
        if not self._use_temp_db:
            return
        save_state(
            FullState(
                tasks=self._tasks,
                workroom=self._workroom,
                timelines=self._timelines,
                declined=list(self._declined_task_ids),
                profile=self._profile,
            ),
            self._db_path,
        )

    def _contributor_profile(self) -> dict[str, Any]:
        return self._profile

    def _skills_matched(self, required: list[str]) -> list[str]:
        prof = self._contributor_profile()
        tags = prof["skill_tags"]
        matched: list[str] = []
        for s in required:
            if s.lower().replace(" ", "_") in tags or s.lower() in tags:
                matched.append(s)
            else:
                for tag in tags:
                    if tag in s.lower():
                        matched.append(s)
                        break
        return list(dict.fromkeys(matched))

    def _active_offer_count(self) -> int:
        now = _utcnow()
        n = 0
        for t in self._tasks.values():
            if t["id"] in self._declined_task_ids:
                continue
            if t["status"] != TaskStatus.available:
                continue
            exp = t.get("offer_expires_at")
            if exp is not None and exp <= now:
                continue
            n += 1
        return n

    def discovery_summary(self) -> DiscoverySummary:
        return DiscoverySummary(active_offers=self._active_offer_count(), server_time=_utcnow())

    def summary(self) -> TaskSummaryKPI:
        counts = {s: 0 for s in TaskStatus}
        for t in self._tasks.values():
            counts[t["status"]] = counts.get(t["status"], 0) + 1
        return TaskSummaryKPI(
            available=counts.get(TaskStatus.available, 0),
            in_progress=counts.get(TaskStatus.in_progress, 0),
            submitted=counts.get(TaskStatus.submitted, 0),
            completed=counts.get(TaskStatus.completed, 0),
            rework=counts.get(TaskStatus.rework, 0),
            active_offers=self._active_offer_count(),
        )

    def _task_to_list_item(self, t: dict[str, Any]) -> TaskListItem:
        p = t["pricing"]
        pricing = Pricing(amount=p["amount"], currency=p["currency"], model=p["model"])
        prof = self._contributor_profile()
        eh = t.get("estimated_hours")
        return TaskListItem(
            id=t["id"],
            title=t["title"],
            project_title=t["project_title"],
            milestone_title=t["milestone_title"],
            status=t["status"],
            priority=t["priority"],
            skills_required=list(t["skills_required"]),
            estimated_hours=eh,
            pricing=pricing,
            match_score=t.get("match_score"),
            match_reason=t.get("match_reason"),
            due_date=t.get("due_date"),
            sla_deadline=t.get("sla_deadline"),
            progress_percent=t.get("progress_percent"),
            hours_logged=t.get("hours_logged"),
            domain_tag=t.get("domain_tag"),
            seniority_required=t.get("seniority_required"),
            contributor_seniority=prof["seniority"],
            skills_matched=self._skills_matched(list(t["skills_required"])),
            offer_expires_at=t.get("offer_expires_at"),
            offered_at=t.get("offered_at"),
            data_sensitivity=t.get("data_sensitivity"),
            nda_required=bool(t.get("nda_required", False)),
            effort_display=t.get("effort_display") or _effort_display(eh),
        )

    def _passes_effort(self, t: dict[str, Any], effort: EffortFilter | None) -> bool:
        if effort is None:
            return True
        h = t.get("estimated_hours")
        if h is None:
            return False
        if effort == EffortFilter.small:
            return h < 8
        if effort == EffortFilter.medium:
            return 8 <= h < 24
        return h >= 24

    def _passes_deadline_within(self, t: dict[str, Any], dw: DeadlineWithinDiscovery | None) -> bool:
        if dw is None:
            return True
        d = t.get("due_date")
        if d is None:
            return False
        today = _utcnow().date()
        if dw == DeadlineWithinDiscovery.week_1:
            return today <= d <= today + timedelta(days=7)
        if dw == DeadlineWithinDiscovery.weeks_2:
            return today <= d <= today + timedelta(days=14)
        return today <= d <= today + timedelta(days=31)

    def list_tasks(
        self,
        *,
        status: TaskStatus | None,
        priority: TaskPriority | None,
        time_filter: TimeFilter | None,
        q: str | None,
        sort_by: TaskSortBy,
        sort_dir: str,
        page: int,
        page_size: int,
        discovery_feed: bool = False,
        skill_tag: str | None = None,
        effort: EffortFilter | None = None,
        deadline_within: DeadlineWithinDiscovery | None = None,
    ) -> tuple[list[TaskListItem], int]:
        now = _utcnow()
        items = list(self._tasks.values())
        if discovery_feed:
            items = [
                t
                for t in items
                if t["status"] == TaskStatus.available
                and t["id"] not in self._declined_task_ids
                and (t.get("offer_expires_at") is None or t["offer_expires_at"] > now)
            ]
        if status is not None:
            items = [t for t in items if t["status"] == status]
        if priority is not None:
            items = [t for t in items if t["priority"] == priority]
        if time_filter is not None:
            today = _utcnow().date()
            if time_filter == TimeFilter.week:
                end = today + timedelta(days=7)

                def in_week(t: dict[str, Any]) -> bool:
                    d = t.get("due_date")
                    return d is not None and today <= d <= end

                items = [t for t in items if in_week(t)]
            else:
                end = today + timedelta(days=31)

                def in_month(t: dict[str, Any]) -> bool:
                    d = t.get("due_date")
                    return d is not None and today <= d <= end

                items = [t for t in items if in_month(t)]
        if skill_tag:
            st = skill_tag.strip().lower()
            items = [t for t in items if any(st in s.lower() for s in t["skills_required"])]
        items = [t for t in items if self._passes_effort(t, effort)]
        items = [t for t in items if self._passes_deadline_within(t, deadline_within)]
        if q:
            ql = q.lower()
            items = [
                t
                for t in items
                if ql in t["title"].lower()
                or ql in t["project_title"].lower()
                or any(ql in s.lower() for s in t["skills_required"])
            ]

        priority_order = {
            TaskPriority.urgent: 0,
            TaskPriority.high: 1,
            TaskPriority.medium: 2,
            TaskPriority.low: 3,
        }
        status_order = {s: i for i, s in enumerate(TaskStatus)}
        reverse = sort_dir == "desc"

        def sort_key(t: dict[str, Any]) -> Any:
            if sort_by == TaskSortBy.task:
                return t["title"].lower()
            if sort_by == TaskSortBy.project:
                return t["project_title"].lower()
            if sort_by == TaskSortBy.status:
                return status_order.get(t["status"], 99)
            if sort_by == TaskSortBy.priority:
                return priority_order.get(t["priority"], 99)
            if sort_by == TaskSortBy.match:
                return t.get("match_score") or 0.0
            if sort_by == TaskSortBy.due_date:
                return t.get("due_date") or date.max
            if sort_by == TaskSortBy.pricing:
                return t["pricing"]["amount"]
            if sort_by == TaskSortBy.offer_expiry:
                exp = t.get("offer_expires_at")
                return exp or datetime(9999, 12, 31, tzinfo=timezone.utc)
            if sort_by == TaskSortBy.shortest_effort:
                return t.get("estimated_hours") if t.get("estimated_hours") is not None else 1e9
            if sort_by == TaskSortBy.recent:
                return t.get("offered_at") or datetime.min.replace(tzinfo=timezone.utc)
            return t["id"]

        items.sort(key=sort_key, reverse=reverse)

        total = len(items)
        start = (page - 1) * page_size
        slice_ = items[start : start + page_size]
        return [self._task_to_list_item(t) for t in slice_], total

    def get_task(self, task_id: str) -> TaskDetail | None:
        t = self._tasks.get(task_id)
        if not t:
            return None
        p = t["pricing"]
        pricing = Pricing(amount=p["amount"], currency=p["currency"], model=p["model"])
        prof = self._contributor_profile()
        eh = t.get("estimated_hours")
        refs = [ReferenceMaterial(**r) for r in t.get("reference_materials", [])]
        return TaskDetail(
            id=t["id"],
            project_id=t["project_id"],
            project_title=t["project_title"],
            milestone_title=t["milestone_title"],
            title=t["title"],
            description=t["description"],
            status=t["status"],
            priority=t["priority"],
            skills_required=list(t["skills_required"]),
            estimated_hours=eh,
            pricing=pricing,
            match_score=t.get("match_score"),
            match_reason=t.get("match_reason"),
            due_date=t.get("due_date"),
            sla_deadline=t.get("sla_deadline"),
            assigned_at=t.get("assigned_at"),
            started_at=t.get("started_at"),
            submitted_at=t.get("submitted_at"),
            accepted_at=t.get("accepted_at"),
            review_score=t.get("review_score"),
            review_comment=t.get("review_comment"),
            rework_reason=t.get("rework_reason"),
            rework_deadline=t.get("rework_deadline"),
            acceptance_criteria=list(t.get("acceptance_criteria", [])),
            evidence_types_required=list(t.get("evidence_types_required", [])),
            milestone_number=t.get("milestone_number"),
            reference_materials=refs,
            reviewer_guidance_preview=t.get("reviewer_guidance_preview"),
            domain_tag=t.get("domain_tag"),
            seniority_required=t.get("seniority_required"),
            contributor_seniority=prof["seniority"],
            skills_matched=self._skills_matched(list(t["skills_required"])),
            offer_expires_at=t.get("offer_expires_at"),
            offered_at=t.get("offered_at"),
            data_sensitivity=t.get("data_sensitivity"),
            nda_required=bool(t.get("nda_required", False)),
            effort_display=t.get("effort_display") or _effort_display(eh),
        )

    def accept_impact(self, task_id: str) -> AcceptImpactResponse | None:
        t = self._tasks.get(task_id)
        if not t:
            return None
        prof = self._contributor_profile()
        declared = float(prof["declared_hours_per_week"])
        current_week = float(prof["hours_committed_this_week"])
        task_h = float(t.get("estimated_hours") or 0.0)
        after = current_week + task_h
        pct = round((after / declared) * 100.0, 1) if declared > 0 else 0.0
        would_exceed = after > declared
        advisory = (not would_exceed) and (90.0 <= pct <= 100.0)

        active = sum(1 for x in self._tasks.values() if x["status"] == TaskStatus.in_progress)

        due = t.get("due_date")
        notice: str | None = None
        if due is not None:
            y, w, _ = due.isocalendar()
            others_same_week = 0
            for x in self._tasks.values():
                if x["id"] == task_id:
                    continue
                if x["status"] not in (TaskStatus.in_progress, TaskStatus.available):
                    continue
                xd = x.get("due_date")
                if xd is None:
                    continue
                yy, ww, _ = xd.isocalendar()
                if yy == y and ww == w:
                    others_same_week += 1
            total_in_week = 1 + others_same_week
            if total_in_week >= 3:
                notice = (
                    f"You already have {others_same_week} tasks with deadlines in the week of {due.isoformat()}; "
                    f"accepting adds this task ({total_in_week} total that week)."
                )

        return AcceptImpactResponse(
            current_active_tasks=active,
            hours_committed_this_week=current_week,
            declared_hours_per_week=declared,
            task_estimated_hours=task_h,
            after_accept_weekly_hours=round(after, 2),
            capacity_percent_after=pct,
            would_exceed_capacity=would_exceed,
            advisory_near_capacity=advisory,
            concurrent_deadlines_notice=notice,
            accept_allowed=not would_exceed,
        )

    def _append_timeline(self, task_id: str, event_type: str, label: str, metadata: dict[str, Any] | None = None) -> None:
        ev = {
            "id": f"ev_{uuid.uuid4().hex[:12]}",
            "event_type": event_type,
            "at": _utcnow(),
            "label": label,
            "metadata": metadata or {},
        }
        self._timelines.setdefault(task_id, []).append(ev)

    def accept(self, task_id: str, body: AcceptBody) -> bool:
        t = self._tasks.get(task_id)
        if not t:
            return False
        impact = self.accept_impact(task_id)
        if impact is not None and not impact.accept_allowed:
            return False
        t["accepted_at"] = body.accepted_at or _utcnow()
        t["assigned_at"] = t["assigned_at"] or t["accepted_at"]
        if t["status"] == TaskStatus.available:
            t["status"] = TaskStatus.in_progress
        self._append_timeline(task_id, "accepted", "Task accepted", {"note": body.note})
        self._persist()
        return True

    def decline(self, task_id: str, body: DeclineBody) -> bool:
        if task_id not in self._tasks:
            return False
        self._declined_task_ids.add(task_id)
        meta: dict[str, Any] = {"notes": body.notes}
        if body.reason is not None:
            meta["reason"] = body.reason.value
        self._append_timeline(task_id, "declined", "Task declined", meta)
        self._persist()
        return True

    def start(self, task_id: str, body: StartBody) -> bool:
        t = self._tasks.get(task_id)
        if not t:
            return False
        t["started_at"] = body.started_at or _utcnow()
        t["status"] = TaskStatus.in_progress
        self._append_timeline(task_id, "started", "Work started")
        self._persist()
        return True

    def request_extension(self, task_id: str, body: RequestExtensionBody) -> bool:
        t = self._tasks.get(task_id)
        if not t:
            return False
        t["due_date"] = body.requested_due_date
        self._append_timeline(
            task_id,
            "extension_requested",
            "Extension requested",
            {
                "requested_due_date": body.requested_due_date.isoformat(),
                "reason": body.reason,
                "notes": body.notes,
                "supporting_attachment_ids": body.supporting_attachment_ids,
            },
        )
        self._persist()
        return True

    def timeline(self, task_id: str) -> list[TimelineEvent]:
        raw = self._timelines.get(task_id, [])
        return [
            TimelineEvent(
                id=e["id"],
                event_type=e["event_type"],
                at=e["at"],
                label=e["label"],
                metadata=e.get("metadata") or {},
            )
            for e in sorted(raw, key=lambda x: x["at"])
        ]

    def workroom(self, task_id: str) -> WorkroomView | None:
        t = self._tasks.get(task_id)
        w = self._workroom.get(task_id)
        if not t or not w:
            return None
        templates = [WorkroomTemplate(**x) for x in w["templates"]]
        links = [WorkroomLink(**x) for x in w["links"]]
        uploads = [WorkroomUpload(**x) for x in w["uploads"]]
        qa = [QAMessage(**x) for x in w["qa_messages"]]
        checklist = [EvidenceChecklistItem(**x) for x in w["evidence_checklist"]]
        return WorkroomView(
            instructions=w["instructions"],
            templates=templates,
            links=links,
            uploads=uploads,
            qa_messages=qa,
            evidence_checklist=checklist,
            progress_percent=t.get("progress_percent"),
            hours_logged=t.get("hours_logged"),
            last_activity_at=w.get("last_activity_at"),
        )

    def post_message(self, task_id: str, body: PostWorkroomMessageBody) -> QAMessage | None:
        if task_id not in self._tasks or task_id not in self._workroom:
            return None
        msg = {
            "id": f"qa_{uuid.uuid4().hex[:10]}",
            "author": "contributor",
            "message": body.message,
            "created_at": _utcnow(),
            "attachment_ids": list(body.attachment_ids),
        }
        self._workroom[task_id]["qa_messages"].append(msg)
        self._workroom[task_id]["last_activity_at"] = _utcnow()
        self._persist()
        return QAMessage(**msg)

    def list_messages(self, task_id: str, page: int, page_size: int) -> tuple[list[QAMessage], int] | None:
        w = self._workroom.get(task_id)
        if not w:
            return None
        msgs = [QAMessage(**x) for x in w["qa_messages"]]
        msgs.sort(key=lambda m: m.created_at)
        total = len(msgs)
        start = (page - 1) * page_size
        return msgs[start : start + page_size], total

    def add_upload(
        self,
        task_id: str,
        *,
        filename: str,
        category: UploadCategory,
        title: str | None,
        description: str | None,
    ) -> UploadResponse | None:
        if task_id not in self._tasks or task_id not in self._workroom:
            return None
        upl_id = f"upl_{uuid.uuid4().hex[:10]}"
        now = _utcnow()
        row = {
            "id": upl_id,
            "filename": filename,
            "category": category,
            "title": title,
            "description": description,
            "uploaded_at": now,
            "size_bytes": None,
        }
        self._workroom[task_id]["uploads"].append(row)
        self._workroom[task_id]["last_activity_at"] = now
        self._persist()
        return UploadResponse(
            id=upl_id,
            filename=filename,
            category=category,
            title=title,
            description=description,
            uploaded_at=now,
        )

    def delete_upload(self, task_id: str, upload_id: str) -> bool:
        w = self._workroom.get(task_id)
        if not w:
            return False
        before = len(w["uploads"])
        w["uploads"] = [u for u in w["uploads"] if u["id"] != upload_id]
        ok = len(w["uploads"]) < before
        if ok:
            self._persist()
        return ok

    def patch_checklist(self, task_id: str, item_id: str, body: ChecklistPatchBody) -> EvidenceChecklistItem | None:
        w = self._workroom.get(task_id)
        if not w:
            return None
        for item in w["evidence_checklist"]:
            if item["id"] == item_id:
                item["completed"] = body.completed
                if body.evidence_file_id is not None:
                    item["evidence_file_id"] = body.evidence_file_id
                if body.notes is not None:
                    item["notes"] = body.notes
                w["last_activity_at"] = _utcnow()
                self._persist()
                return EvidenceChecklistItem(**item)
        return None

    def templates(self, task_id: str) -> list[WorkroomTemplate] | None:
        w = self._workroom.get(task_id)
        if not w:
            return None
        return [WorkroomTemplate(**x) for x in w["templates"]]

    def links(self, task_id: str) -> list[WorkroomLink] | None:
        w = self._workroom.get(task_id)
        if not w:
            return None
        return [WorkroomLink(**x) for x in w["links"]]


_task_services: dict[str, ContributorTaskService] = {}
_task_services_lock = RLock()


def get_contributor_task_service(
    contributor_id: Annotated[str, Depends(get_contributor_id)],
) -> ContributorTaskService:
    """One task service (and SQLite file) per authenticated contributor."""
    with _task_services_lock:
        svc = _task_services.get(contributor_id)
        if svc is None:
            svc = ContributorTaskService(contributor_id=contributor_id)
            _task_services[contributor_id] = svc
        return svc


def reset_task_service_singleton() -> None:
    """Clear cached task services (e.g. after wiping temp_api_db while stopped)."""
    global _task_services
    with _task_services_lock:
        _task_services.clear()

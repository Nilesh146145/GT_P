from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from app.contributor.schemas.dashboard import (
    ActiveTask,
    ContributorDashboard,
    ContributorMe,
    CredentialItem,
    DashboardActionItem,
    DashboardKpi,
    EarningsSnapshot,
    LearningItem,
    NotificationItem,
    RecentEarning,
    SkillItem,
    SystemBanner,
)

# Primary: temp_api_db/dashboard.json (created by demo_bootstrap). Fallback: built-in demo data.
_TEMP_DATA_FILE = Path(__file__).resolve().parents[2] / "temp_api_db" / "dashboard.json"

_now = datetime.now(UTC)


def _builtin_contributor_me() -> ContributorMe:
    return ContributorMe(
        id="ctr_01hqz8k2example",
        display_name="Alex Contributor",
        anonymous_id="anon_7f3c9a2b1d",
        avatar="https://example.com/avatars/default.png",
        email="alex@example.com",
        track="data_labeling",
        designation="Contributor",
        seniority_level="Senior",
        verification_status="verified",
        timezone="America/New_York",
        availability="20h/week",
        last_availability_updated_at=(_now - timedelta(days=10))
        .isoformat()
        .replace("+00:00", "Z"),
        profile_completeness=0.85,
        onboarding_complete=True,
        assessment_status="none",
        kyc_required=False,
        kyc_status="verified",
    )


def _builtin_dashboard_base() -> ContributorDashboard:
    return ContributorDashboard(
        greeting_name="Alex",
        kpis=[
            DashboardKpi(key="tasks_week", label="Tasks this week", value=12, trend="up"),
            DashboardKpi(
                key="earnings_month",
                label="Earnings (month)",
                value="$240",
                trend="flat",
            ),
            DashboardKpi(key="quality", label="Quality score", value=98, trend="up"),
        ],
        earnings_snapshot=EarningsSnapshot(
            currency="USD",
            earned_this_month=240.0,
            total_paid_all_time=4200.0,
            pending_payout=85.5,
        ),
        action_items=[
            DashboardActionItem(
                id="act_1",
                kind="deadline_tomorrow",
                urgency="high",
                title="Deadline tomorrow",
                subtitle="Image batch #42",
                task_id="tsk_101",
                cta_label="Open workroom",
                cta_href="/tasks/tsk_101/workroom",
            ),
            DashboardActionItem(
                id="act_2",
                kind="payment_ready",
                urgency="medium",
                title="Payment ready",
                subtitle="$85.50 pending confirmation",
                cta_label="View earnings",
                cta_href="/earnings",
            ),
        ],
        system_banners=[
            SystemBanner(
                id="bnr_avail",
                variant="amber",
                title="Update your availability",
                body="Your availability was last updated 10 days ago. Confirm it to keep receiving relevant offers.",
                cta_label="Update now",
                cta_href="/profile/availability",
                dismissible=True,
            ),
        ],
        active_tasks=[
            ActiveTask(
                id="tsk_101",
                title="Image batch #42",
                project_title="Acme Vision",
                milestone_title="Batch 2",
                status="in_progress",
                due_at=(_now + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                due_relative="Tomorrow",
                priority="normal",
                workroom_path="/tasks/tsk_101/workroom",
            ),
        ],
        recent_earnings=[
            RecentEarning(
                id="ern_01",
                amount=45.5,
                currency="USD",
                label="Batch completion bonus",
                earned_at=(_now - timedelta(hours=12)).isoformat().replace("+00:00", "Z"),
            ),
        ],
        credentials=[
            CredentialItem(
                id="cred_1",
                name="Contributor fundamentals",
                issuer="Glimmora",
                status="active",
                expires_at=None,
            ),
        ],
        skills=[
            SkillItem(id="sk_1", name="Image annotation", level="intermediate"),
            SkillItem(id="sk_2", name="QA review", level="beginner"),
        ],
        notifications=[],
        recommended_learning=[
            LearningItem(
                id="lrn_1",
                title="Advanced labeling quality",
                url="https://example.com/learn/advanced-labeling",
                duration_minutes=25,
                reason="Matches your current track",
            ),
        ],
    )


def _builtin_notifications() -> list[NotificationItem]:
    return [
        NotificationItem(
            id="ntf_001",
            type="task",
            title="New task assigned",
            body="You have a new labeling batch ready.",
            read=False,
            created_at=(_now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        ),
        NotificationItem(
            id="ntf_002",
            type="payout",
            title="Payout processed",
            body="Your last payout was sent to your account.",
            read=True,
            created_at=(_now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        ),
        NotificationItem(
            id="ntf_003",
            type="system",
            title="Policy update",
            body="Please review the updated contributor guidelines.",
            read=False,
            created_at=(_now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        ),
    ]


def _load_temp_file() -> tuple[ContributorMe, ContributorDashboard, list[NotificationItem]] | None:
    if not _TEMP_DATA_FILE.is_file():
        return None
    try:
        raw = json.loads(_TEMP_DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw.pop("_readme", None)
    if not isinstance(raw, dict):
        return None
    try:
        me = ContributorMe.model_validate(raw["contributor_me"])
        dash_in = dict(raw["dashboard"])
        dash_in["notifications"] = []
        full = ContributorDashboard.model_validate(dash_in)
        notes = [NotificationItem.model_validate(n) for n in raw["notifications"]]
    except (KeyError, ValueError, ValidationError):
        return None
    return me, full, notes


_seed = _load_temp_file()
if _seed:
    CONTRIBUTOR_ME, _FULL_DASHBOARD_BASE, _notifications = _seed
    _notifications = list(_notifications)
else:
    CONTRIBUTOR_ME = _builtin_contributor_me()
    _FULL_DASHBOARD_BASE = _builtin_dashboard_base()
    _notifications = _builtin_notifications()

INCLUDE_MAP: dict[str, str] = {
    "notifications": "notifications",
    "activeTasks": "active_tasks",
    "earnings": "recent_earnings",
    "credentials": "credentials",
    "learning": "recommended_learning",
}

_EMPTY_KEYS: dict[str, list] = {
    "notifications": [],
    "active_tasks": [],
    "recent_earnings": [],
    "credentials": [],
    "recommended_learning": [],
}


def _sync_notifications_into_dashboard(d: ContributorDashboard) -> None:
    d.notifications = [copy.deepcopy(n) for n in _notifications]


def get_contributor_me() -> ContributorMe:
    return CONTRIBUTOR_ME.model_copy()


def get_dashboard(include: str | None) -> ContributorDashboard:
    full = _FULL_DASHBOARD_BASE.model_copy(deep=True)
    _sync_notifications_into_dashboard(full)

    base = ContributorDashboard(
        greeting_name=full.greeting_name,
        kpis=[k.model_copy() for k in full.kpis],
        earnings_snapshot=full.earnings_snapshot.model_copy(),
        action_items=[a.model_copy() for a in full.action_items],
        system_banners=[b.model_copy() for b in full.system_banners],
        active_tasks=[],
        recent_earnings=[],
        credentials=[],
        skills=[s.model_copy() for s in full.skills],
        notifications=[],
        recommended_learning=[],
    )

    if not include or not include.strip():
        out = full.model_copy(deep=True)
        _sync_notifications_into_dashboard(out)
        return out

    parts = [p.strip() for p in include.split(",") if p.strip()]
    data = full.model_dump()
    out_dict = base.model_dump()

    for p in parts:
        key = INCLUDE_MAP.get(p)
        if not key:
            continue
        out_dict[key] = copy.deepcopy(data[key])

    for inc_key, field in INCLUDE_MAP.items():
        if inc_key not in parts:
            out_dict[field] = copy.deepcopy(_EMPTY_KEYS[field])

    out = ContributorDashboard.model_validate(out_dict)
    _sync_notifications_into_dashboard(out)
    return out


def list_notifications_filtered(
    *,
    page: int,
    page_size: int,
    read: bool | None,
    type_: str | None,
) -> tuple[list[NotificationItem], int]:
    items = [n.model_copy() for n in _notifications]
    if read is not None:
        items = [n for n in items if n.read is read]
    if type_:
        items = [n for n in items if n.type == type_]
    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    return page_items, total


def set_notification_read(notification_id: str, read: bool) -> bool:
    for n in _notifications:
        if n.id == notification_id:
            n.read = read
            return True
    return False


def mark_all_notifications_read() -> int:
    count = 0
    for n in _notifications:
        if not n.read:
            n.read = True
            count += 1
    return count


def get_notification_by_id(notification_id: str) -> NotificationItem | None:
    for n in _notifications:
        if n.id == notification_id:
            return n.model_copy()
    return None


def apply_e2e_dashboard_alignment() -> None:
    """Align dashboard task IDs with SQLite-seeded tasks (tsk_001–tsk_006); add notification types for E2E."""
    global _FULL_DASHBOARD_BASE, _notifications

    repl = {
        "tsk_demo_201": "tsk_002",
        "tsk_demo_202": "tsk_003",
        "tsk_demo_103": "tsk_005",
    }

    def remap_href(href: str | None) -> str | None:
        if not href:
            return href
        out = href
        for old, new in repl.items():
            out = out.replace(old, new)
        return out

    base = _FULL_DASHBOARD_BASE
    new_tasks: list[ActiveTask] = []
    for t in base.active_tasks:
        nid = repl.get(t.id, t.id)
        new_tasks.append(
            t.model_copy(
                update={
                    "id": nid,
                    "workroom_path": f"/tasks/{nid}/workroom",
                }
            )
        )

    new_actions: list[DashboardActionItem] = []
    for a in base.action_items:
        tid = a.task_id
        if tid and tid in repl:
            tid = repl[tid]
        new_actions.append(
            a.model_copy(
                update={
                    "task_id": tid,
                    "cta_href": remap_href(a.cta_href),
                }
            )
        )

    new_banners: list[SystemBanner] = []
    for b in base.system_banners:
        tid = b.task_id
        if tid and tid in repl:
            tid = repl[tid]
        new_banners.append(
            b.model_copy(
                update={
                    "task_id": tid,
                    "cta_href": remap_href(b.cta_href),
                }
            )
        )

    new_recent: list[RecentEarning] = []
    for re in base.recent_earnings:
        rid = re.id
        if rid == "ern_01":
            rid = "ern_001"
        elif rid == "ern_02":
            rid = "ern_002"
        elif rid == "ern_03":
            rid = "ern_004"
        new_recent.append(re.model_copy(update={"id": rid}))

    _FULL_DASHBOARD_BASE = base.model_copy(
        update={
            "active_tasks": new_tasks,
            "action_items": new_actions,
            "system_banners": new_banners,
            "recent_earnings": new_recent,
        }
    )

    have = {n.id for n in _notifications}
    extras = [
        NotificationItem(
            id="ntf_e2e_review",
            type="review",
            title="Submission reviewed",
            body="Your submission for task tsk_003 is under review.",
            read=False,
            created_at=(_now - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
        ),
        NotificationItem(
            id="ntf_e2e_rework",
            type="task",
            title="Rework requested",
            body="Reviewer left feedback on tsk_005 — open the workroom to continue.",
            read=False,
            created_at=(_now - timedelta(hours=5)).isoformat().replace("+00:00", "Z"),
        ),
        NotificationItem(
            id="ntf_e2e_learning",
            type="learning",
            title="Recommended course",
            body="Complete “REST API design checklist” to strengthen your contributor profile.",
            read=True,
            created_at=(_now - timedelta(days=3)).isoformat().replace("+00:00", "Z"),
        ),
    ]
    for n in extras:
        if n.id not in have:
            _notifications.append(n)

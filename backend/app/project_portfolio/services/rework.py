from __future__ import annotations

from datetime import date, datetime, timezone

UTC = timezone.utc  # Python 3.9 (datetime.UTC is 3.11+)

from app.project_portfolio.schemas.rework import ReworkRequest, ReworkRequestStatus, ReworkRequestsResponse
from app.project_portfolio.services.projects import project_exists


def _dt(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, 17, 0, tzinfo=UTC)


_REWORKS: list[ReworkRequest] = [
    ReworkRequest(
        id="rw_p1_01",
        project_id="proj_001",
        task_id="tk_proj_001_t2",
        task="UI sign-off",
        milestone_id="ms_proj_001_m1",
        milestone="Design freeze (M1)",
        reason="Contrast fails WCAG AA on primary buttons.",
        deadline=_dt(2026, 3, 22),
        round=1,
        status=ReworkRequestStatus.OPEN,
    ),
    ReworkRequest(
        id="rw_p1_02",
        project_id="proj_001",
        task_id="tk_proj_001_t4",
        task="Regression QA",
        milestone_id="ms_proj_001_m2",
        milestone="Build & QA (M2)",
        reason="Blocking defects in checkout flow; need retest pass.",
        deadline=_dt(2026, 4, 12),
        round=2,
        status=ReworkRequestStatus.IN_PROGRESS,
    ),
    ReworkRequest(
        id="rw_p1_03",
        project_id="proj_001",
        task_id="tk_proj_001_t3",
        task="Implementation",
        milestone_id="ms_proj_001_m2",
        milestone="Build & QA (M2)",
        reason="API latency SLO breach on report export.",
        deadline=_dt(2026, 4, 8),
        round=1,
        status=ReworkRequestStatus.OPEN,
    ),
    ReworkRequest(
        id="rw_p2_01",
        project_id="proj_002",
        task_id="tk_proj_002_t1",
        task="Ingest job",
        milestone_id="ms_proj_002_m1",
        milestone="Pipeline MVP (M1)",
        reason="Schema drift on events_v2 table.",
        deadline=_dt(2026, 3, 28),
        round=1,
        status=ReworkRequestStatus.OPEN,
    ),
]


def _matches_milestone(rework: ReworkRequest, milestone_id: str | None) -> bool:
    if not milestone_id:
        return True
    raw = milestone_id.strip()
    if not raw:
        return True
    if raw == rework.milestone_id:
        return True
    if len(raw) <= 4 and raw.upper().startswith("M"):
        return raw.upper() in rework.milestone.upper()
    return False


def get_rework_request(project_id: str, rework_id: str) -> ReworkRequest | None:
    for rework in _REWORKS:
        if rework.id == rework_id and rework.project_id == project_id:
            return rework
    return None


def mark_rework_escalated(project_id: str, rework_id: str) -> bool:
    for index, rework in enumerate(_REWORKS):
        if rework.id == rework_id and rework.project_id == project_id:
            _REWORKS[index] = rework.model_copy(update={"status": ReworkRequestStatus.ESCALATED})
            return True
    return False


def list_rework_requests(
    project_id: str,
    *,
    status: ReworkRequestStatus | None,
    milestone_id: str | None,
    round_eq: int | None,
    task_query: str | None,
    deadline_from: date | None,
    deadline_to: date | None,
    page: int,
    limit: int,
) -> ReworkRequestsResponse | None:
    if not project_exists(project_id):
        return None
    rows = [row for row in _REWORKS if row.project_id == project_id]
    filtered: list[ReworkRequest] = []
    task_filter = (task_query or "").strip().lower()
    for row in rows:
        if status is not None and row.status != status:
            continue
        if not _matches_milestone(row, milestone_id):
            continue
        if round_eq is not None and row.round != round_eq:
            continue
        if task_filter and task_filter not in row.task.lower():
            continue
        deadline_value = row.deadline.date()
        if deadline_from is not None and deadline_value < deadline_from:
            continue
        if deadline_to is not None and deadline_value > deadline_to:
            continue
        filtered.append(row)

    filtered.sort(key=lambda row: (row.deadline, row.id))
    total = len(filtered)
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit
    page_rows = filtered[offset : offset + limit]

    return ReworkRequestsResponse(
        project_id=project_id,
        page=page,
        limit=limit,
        total=total,
        status_filter=status,
        milestone_filter=milestone_id.strip() if milestone_id else None,
        round_filter=round_eq,
        task_query=task_query.strip() if task_query else None,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        rework_requests=page_rows,
    )


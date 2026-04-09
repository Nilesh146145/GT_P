from datetime import UTC, datetime

from app.project_portfolio.schemas.timeline import (
    MilestoneDetail,
    ProjectTimelineResponse,
    TimelineMilestone,
    TimelineTask,
    TimelineView,
)
from app.project_portfolio.services.projects import project_exists

_TIMELINES: dict[str, list[TimelineMilestone]] = {
    "proj_001": [
        TimelineMilestone(
            id="ms_proj_001_m1",
            name="Design freeze",
            start_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 20, 17, 0, tzinfo=UTC),
            status="in_progress",
            tasks=[
                TimelineTask(
                    id="tk_proj_001_t1",
                    title="Wireframes",
                    start_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
                    end_at=datetime(2026, 3, 8, 17, 0, tzinfo=UTC),
                    status="done",
                    depends_on_task_ids=[],
                ),
                TimelineTask(
                    id="tk_proj_001_t2",
                    title="UI sign-off",
                    start_at=datetime(2026, 3, 9, 9, 0, tzinfo=UTC),
                    end_at=datetime(2026, 3, 20, 17, 0, tzinfo=UTC),
                    status="in_progress",
                    depends_on_task_ids=["tk_proj_001_t1"],
                ),
            ],
        ),
        TimelineMilestone(
            id="ms_proj_001_m2",
            name="Build & QA",
            start_at=datetime(2026, 3, 21, 9, 0, tzinfo=UTC),
            end_at=datetime(2026, 4, 15, 17, 0, tzinfo=UTC),
            status="planned",
            tasks=[
                TimelineTask(
                    id="tk_proj_001_t3",
                    title="Implementation",
                    start_at=datetime(2026, 3, 21, 9, 0, tzinfo=UTC),
                    end_at=datetime(2026, 4, 8, 17, 0, tzinfo=UTC),
                    status="todo",
                    depends_on_task_ids=["tk_proj_001_t2"],
                ),
                TimelineTask(
                    id="tk_proj_001_t4",
                    title="Regression QA",
                    start_at=datetime(2026, 4, 9, 9, 0, tzinfo=UTC),
                    end_at=datetime(2026, 4, 15, 17, 0, tzinfo=UTC),
                    status="todo",
                    depends_on_task_ids=["tk_proj_001_t3"],
                ),
            ],
        ),
    ],
    "proj_002": [
        TimelineMilestone(
            id="ms_proj_002_m1",
            name="Pipeline MVP",
            start_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
            end_at=datetime(2026, 4, 1, 17, 0, tzinfo=UTC),
            status="in_progress",
            tasks=[
                TimelineTask(
                    id="tk_proj_002_t1",
                    title="Ingest job",
                    start_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
                    end_at=datetime(2026, 3, 22, 17, 0, tzinfo=UTC),
                    status="in_progress",
                    depends_on_task_ids=[],
                ),
            ],
        ),
    ],
    "proj_003": [
        TimelineMilestone(
            id="ms_proj_003_m1",
            name="Beta readiness",
            start_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
            end_at=datetime(2026, 4, 30, 17, 0, tzinfo=UTC),
            status="at_risk",
            tasks=[
                TimelineTask(
                    id="tk_proj_003_t1",
                    title="Crash triage",
                    start_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
                    end_at=datetime(2026, 4, 14, 17, 0, tzinfo=UTC),
                    status="todo",
                    depends_on_task_ids=[],
                ),
            ],
        ),
    ],
    "proj_004": [
        TimelineMilestone(
            id="ms_proj_004_m1",
            name="Retrospective",
            start_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
            end_at=datetime(2026, 4, 10, 17, 0, tzinfo=UTC),
            status="done",
            tasks=[
                TimelineTask(
                    id="tk_proj_004_t1",
                    title="Publish recap",
                    start_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
                    end_at=datetime(2026, 4, 10, 17, 0, tzinfo=UTC),
                    status="done",
                    depends_on_task_ids=[],
                ),
            ],
        ),
    ],
}

_MILESTONE_INDEX: dict[str, tuple[str, TimelineMilestone]] = {}
for _pid, _milestones in _TIMELINES.items():
    for _m in _milestones:
        _MILESTONE_INDEX[_m.id] = (_pid, _m)


def get_project_timeline(project_id: str, view: TimelineView) -> ProjectTimelineResponse | None:
    if not project_exists(project_id):
        return None
    milestones = _TIMELINES.get(project_id, [])
    milestones_out = list(milestones)
    if view == TimelineView.GANTT:
        milestones_out = sorted(milestones_out, key=lambda m: m.start_at)
    else:
        milestones_out = sorted(milestones_out, key=lambda m: (m.start_at, m.name))
    return ProjectTimelineResponse(
        project_id=project_id,
        view=view,
        milestones=milestones_out,
    )


def get_milestone_detail(milestone_id: str) -> MilestoneDetail | None:
    entry = _MILESTONE_INDEX.get(milestone_id)
    if entry is None:
        return None
    project_id, m = entry
    return MilestoneDetail(
        id=m.id,
        project_id=project_id,
        name=m.name,
        description=f"Milestone window {m.start_at.date()} -> {m.end_at.date()}.",
        start_at=m.start_at,
        end_at=m.end_at,
        status=m.status,
        deliverables=[
            "Scope agreed with stakeholders",
            "Exit criteria documented",
        ],
        tasks=list(m.tasks),
    )

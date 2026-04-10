import itertools
from collections import Counter
from datetime import UTC, datetime

from app.project_portfolio.schemas.team import (
    SkillCoverageResponse,
    SkillCoverageRow,
    SkillReviewRequestResponse,
    TeamCompositionResponse,
    TeamTaskItem,
    TaskExecutionStatus,
)
from app.project_portfolio.services.projects import project_exists

_TEAM_BY_PROJECT: dict[str, list[TeamTaskItem]] = {
    "proj_001": [
        TeamTaskItem(
            task_id="tk_proj_001_t1",
            task_title="Wireframes",
            contributors=["Alex Kim", "Jamie Lopez"],
            skills=["UX", "Figma"],
            execution_status=TaskExecutionStatus.DONE,
        ),
        TeamTaskItem(
            task_id="tk_proj_001_t2",
            task_title="UI sign-off",
            contributors=["Alex Kim"],
            skills=["UX", "Accessibility"],
            execution_status=TaskExecutionStatus.IN_PROGRESS,
        ),
        TeamTaskItem(
            task_id="tk_proj_001_t3",
            task_title="Implementation",
            contributors=["Sam Patel", "Riley Chen"],
            skills=["React", "TypeScript"],
            execution_status=TaskExecutionStatus.IN_PROGRESS,
        ),
        TeamTaskItem(
            task_id="tk_proj_001_t4",
            task_title="Regression QA",
            contributors=["Morgan Blake"],
            skills=["QA", "Automation"],
            execution_status=TaskExecutionStatus.NOT_STARTED,
        ),
    ],
    "proj_002": [
        TeamTaskItem(
            task_id="tk_proj_002_t1",
            task_title="Ingest job",
            contributors=["Priya N.", "Jordan M."],
            skills=["Python", "SQL", "Airflow"],
            execution_status=TaskExecutionStatus.IN_PROGRESS,
        ),
    ],
    "proj_003": [
        TeamTaskItem(
            task_id="tk_proj_003_t1",
            task_title="Crash triage",
            contributors=["Casey R."],
            skills=["Mobile", "Sentry"],
            execution_status=TaskExecutionStatus.BLOCKED,
        ),
    ],
    "proj_004": [
        TeamTaskItem(
            task_id="tk_proj_004_t1",
            task_title="Publish recap",
            contributors=["Alex Kim"],
            skills=["Writing", "Notion"],
            execution_status=TaskExecutionStatus.DONE,
        ),
    ],
}

_skill_review_seq = itertools.count(1)
_skill_review_log: list[SkillReviewRequestResponse] = []


def get_team_composition(project_id: str) -> TeamCompositionResponse | None:
    if not project_exists(project_id):
        return None
    tasks = list(_TEAM_BY_PROJECT.get(project_id, []))
    return TeamCompositionResponse(project_id=project_id, tasks=tasks)


def get_skill_coverage(project_id: str) -> SkillCoverageResponse | None:
    if not project_exists(project_id):
        return None
    tasks = _TEAM_BY_PROJECT.get(project_id, [])
    counter: Counter[str] = Counter()
    for task in tasks:
        for skill in task.skills:
            counter[skill] += 1
    rows = [
        SkillCoverageRow(skill=skill, task_count=count)
        for skill, count in sorted(counter.items(), key=lambda x: x[0].lower())
    ]
    return SkillCoverageResponse(project_id=project_id, skills=rows)


def request_skill_coverage_review(
    project_id: str,
    *,
    note: str | None,
) -> SkillReviewRequestResponse | None:
    if not project_exists(project_id):
        return None
    request_id = f"scr_{next(_skill_review_seq):04d}"
    message = "Skill coverage review requested; Admin has been notified (demo: in-memory log only)."
    if note and note.strip():
        message = f"{message} Note recorded."
    record = SkillReviewRequestResponse(
        request_id=request_id,
        project_id=project_id,
        status="submitted",
        created_at=datetime.now(tz=UTC),
        message=message,
    )
    _skill_review_log.append(record)
    return record

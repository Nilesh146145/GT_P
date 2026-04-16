from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response

from app.project_portfolio.schemas.evidence import EvidencePackStatus, EvidencePacksResponse
from app.project_portfolio.schemas.exception import ExceptionCreateRequest, ExceptionsResponse, ProjectException
from app.project_portfolio.schemas.project import (
    ActivityFeedResponse,
    KickoffCreateRequest,
    ProjectDetail,
    ProjectListResponse,
    ProjectOverview,
    ProjectStatusUpdateRequest,
)
from app.project_portfolio.schemas.rework import ReworkRequestStatus, ReworkRequestsResponse
from app.project_portfolio.schemas.timeline import ProjectTimelineResponse, TimelineView
from app.project_portfolio.services.evidence import list_evidence_packs
from app.project_portfolio.services.exceptions import create_exception, list_exceptions
from app.project_portfolio.services.projects import (
    build_project_report_csv,
    create_project_kickoff,
    get_project_detail,
    get_project_overview,
    list_completed_projects,
    list_project_activities,
    set_project_on_hold,
    update_project_status,
)
from app.project_portfolio.services.rework import list_rework_requests
from app.project_portfolio.services.timeline import get_project_timeline

router = APIRouter(tags=["projects"])


@router.post("/projects/kickoff", response_model=ProjectDetail)
def kickoff_project(body: KickoffCreateRequest) -> ProjectDetail:
    detail, err = create_project_kickoff(
        project_id=body.project_id,
        name=body.name,
        summary=body.summary,
        owner=body.owner,
    )
    if err == "project_exists":
        raise HTTPException(status_code=409, detail="Project already exists")
    assert detail is not None
    return detail


@router.get("/projects/completed", response_model=ProjectListResponse)
def view_completed_projects() -> ProjectListResponse:
    return ProjectListResponse(projects=list_completed_projects())


@router.get("/projects/{project_id}/overview", response_model=ProjectOverview)
def get_project_overview_tab(project_id: str) -> ProjectOverview:
    overview = get_project_overview(project_id)
    if overview is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return overview


@router.get("/projects/{project_id}/activities", response_model=ActivityFeedResponse)
def get_project_activities(project_id: str) -> ActivityFeedResponse:
    activities = list_project_activities(project_id)
    if activities is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ActivityFeedResponse(activities=activities)


@router.get("/projects/{project_id}/timeline", response_model=ProjectTimelineResponse)
def get_project_timeline_tab(
    project_id: str,
    view: TimelineView = Query(
        ...,
        description="TAB-2: use `gantt` or `list` (same data; client renders differently).",
    ),
) -> ProjectTimelineResponse:
    timeline = get_project_timeline(project_id, view)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return timeline


@router.get("/projects/{project_id}/evidence-packs", response_model=EvidencePacksResponse)
def get_evidence_packs(
    project_id: str,
    status: EvidencePackStatus | None = Query(
        None,
        description="Filter by pack status, e.g. PENDING_REVIEW",
    ),
    milestone_id: str | None = Query(
        None,
        description="Milestone key (e.g. M2) or full milestone id (e.g. ms_proj_001_m2)",
    ),
    start_date: date | None = Query(
        None,
        description="Inclusive lower bound on submitted_at (date)",
    ),
    end_date: date | None = Query(
        None,
        description="Inclusive upper bound on submitted_at (date)",
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> EvidencePacksResponse:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")

    payload = list_evidence_packs(
        project_id,
        status=status,
        milestone_id=milestone_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return payload


@router.get("/projects/{project_id}/rework-requests", response_model=ReworkRequestsResponse)
def get_rework_requests(
    project_id: str,
    status: ReworkRequestStatus | None = Query(
        None,
        description="Filter by rework status",
    ),
    milestone_id: str | None = Query(
        None,
        description="Milestone key (e.g. M2) or full milestone id",
    ),
    rework_round: int | None = Query(
        None,
        ge=1,
        alias="round",
        description="Exact rework round",
    ),
    task: str | None = Query(
        None,
        description="Substring match on task title",
    ),
    deadline_from: date | None = Query(
        None,
        description="Inclusive: deadline date on/after",
    ),
    deadline_to: date | None = Query(
        None,
        description="Inclusive: deadline date on/before",
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> ReworkRequestsResponse:
    if deadline_from is not None and deadline_to is not None and deadline_from > deadline_to:
        raise HTTPException(status_code=422, detail="deadline_from must be on or before deadline_to")

    payload = list_rework_requests(
        project_id,
        status=status,
        milestone_id=milestone_id,
        round_eq=rework_round,
        task_query=task,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        page=page,
        limit=limit,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return payload


@router.get("/projects/{project_id}/exceptions", response_model=ExceptionsResponse)
def get_project_exceptions(project_id: str) -> ExceptionsResponse:
    rows, err = list_exceptions(project_id)
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    assert rows is not None
    return ExceptionsResponse(project_id=project_id, exceptions=rows)


@router.post("/projects/{project_id}/exceptions", response_model=ProjectException)
def post_project_exception(project_id: str, body: ExceptionCreateRequest) -> ProjectException:
    row, err = create_exception(project_id, body)
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    assert row is not None
    return row


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def view_project(project_id: str) -> ProjectDetail:
    detail = get_project_detail(project_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return detail


@router.post("/projects/{project_id}/status", response_model=ProjectDetail)
def post_project_status(project_id: str, body: ProjectStatusUpdateRequest) -> ProjectDetail:
    detail, err = update_project_status(
        project_id=project_id,
        to_status=body.to_status,
        actor_role=body.actor_role,
    )
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    if err == "invalid_transition":
        raise HTTPException(status_code=409, detail="Invalid status transition")
    if err == "forbidden":
        raise HTTPException(status_code=403, detail="Only manager/admin can set this status")
    assert detail is not None
    return detail


@router.post("/projects/{project_id}/hold", response_model=ProjectDetail)
def hold_project(project_id: str) -> ProjectDetail:
    detail = set_project_on_hold(project_id, on_hold=True)
    if detail is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return detail


@router.post("/projects/{project_id}/resume", response_model=ProjectDetail)
def resume_project(project_id: str) -> ProjectDetail:
    detail = set_project_on_hold(project_id, on_hold=False)
    if detail is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return detail


@router.get("/projects/{project_id}/report")
def download_project_report(project_id: str) -> Response:
    payload = build_project_report_csv(project_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Project not found")
    filename = f"project_{project_id}_report.csv"
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

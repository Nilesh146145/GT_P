from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from starlette.responses import Response

from app.contributor.schemas.tasks import (
    AcceptBody,
    AcceptImpactResponse,
    ActionAck,
    ChecklistPatchBody,
    DeadlineWithinDiscovery,
    DeclineBody,
    DiscoverySummary,
    EffortFilter,
    PaginatedMessages,
    PaginatedTasks,
    PostWorkroomMessageBody,
    RequestExtensionBody,
    StartBody,
    TaskDetail,
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
    WorkroomView,
)
from app.contributor.dependencies import get_contributor_id
from app.contributor.services.contributor_tasks import ContributorTaskService, get_contributor_task_service

router = APIRouter(
    prefix="/api/contributor/tasks",
    tags=["contributor-tasks"],
    dependencies=[Depends(get_contributor_id)],
)


@router.get("/summary", response_model=TaskSummaryKPI)
def tasks_summary(svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)]) -> TaskSummaryKPI:
    return svc.summary()


@router.get("/discovery/summary", response_model=DiscoverySummary)
def discovery_summary(
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> DiscoverySummary:
    """§7.1 — lightweight count for badge refresh (~60s). Also see `active_offers` on GET /summary."""
    return svc.discovery_summary()


@router.get("", response_model=PaginatedTasks)
def list_tasks(
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    time_filter: TimeFilter | None = Query(None, alias="time_filter"),
    q: str | None = None,
    sort_by: TaskSortBy = TaskSortBy.due_date,
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    discovery_feed: bool = Query(False, description="Passive offer feed: available, non-expired, not declined."),
    skill_tag: str | None = Query(None, description="§7.1 Skill Area — match on required skill tags."),
    effort: EffortFilter | None = Query(None, description="§7.1 Effort: small <8h, medium 8–24h, large 24h+."),
    deadline_within: DeadlineWithinDiscovery | None = Query(
        None,
        alias="deadline_within",
        description="§7.1 Timeline filter on due date (1 / 2 weeks or 1 month).",
    ),
) -> PaginatedTasks:
    items, total = svc.list_tasks(
        status=status,
        priority=priority,
        time_filter=time_filter,
        q=q,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
        discovery_feed=discovery_feed,
        skill_tag=skill_tag,
        effort=effort,
        deadline_within=deadline_within,
    )
    return PaginatedTasks(items=items, page=page, page_size=page_size, total=total)


@router.get("/{task_id}/accept-impact", response_model=AcceptImpactResponse)
def get_accept_impact(
    task_id: str,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> AcceptImpactResponse:
    """§7.4 — workload / capacity preview before POST …/accept."""
    out = svc.accept_impact(task_id)
    if not out:
        raise HTTPException(status_code=404, detail="Task not found")
    return out


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(
    task_id: str,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> TaskDetail:
    detail = svc.get_task(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Task not found")
    return detail


@router.post("/{task_id}/accept", response_model=ActionAck)
def accept_task(
    task_id: str,
    body: AcceptBody,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> ActionAck:
    if not svc.get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    if not svc.accept(task_id, body):
        raise HTTPException(
            status_code=409,
            detail="Accept blocked: would exceed declared weekly availability (§7.4).",
        )
    return ActionAck(ok=True, message="accepted")


@router.post("/{task_id}/decline", response_model=ActionAck)
def decline_task(
    task_id: str,
    body: DeclineBody,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> ActionAck:
    if not svc.decline(task_id, body):
        raise HTTPException(status_code=404, detail="Task not found")
    return ActionAck(ok=True, message="declined")


@router.post("/{task_id}/start", response_model=ActionAck)
def start_task(
    task_id: str,
    body: StartBody,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> ActionAck:
    if not svc.start(task_id, body):
        raise HTTPException(status_code=404, detail="Task not found")
    return ActionAck(ok=True, message="started")


@router.post("/{task_id}/request-extension", response_model=ActionAck)
def request_extension(
    task_id: str,
    body: RequestExtensionBody,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> ActionAck:
    if not svc.request_extension(task_id, body):
        raise HTTPException(status_code=404, detail="Task not found")
    return ActionAck(ok=True, message="extension recorded")


@router.get("/{task_id}/timeline", response_model=list[TimelineEvent])
def task_timeline(
    task_id: str,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> list[TimelineEvent]:
    if not svc.get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return svc.timeline(task_id)


@router.get("/{task_id}/workroom", response_model=WorkroomView)
def workroom(
    task_id: str,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> WorkroomView:
    view = svc.workroom(task_id)
    if not view:
        raise HTTPException(status_code=404, detail="Task not found")
    return view


@router.post("/{task_id}/workroom/messages", status_code=201)
def post_workroom_message(
    task_id: str,
    body: PostWorkroomMessageBody,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
):
    msg = svc.post_message(task_id, body)
    if not msg:
        raise HTTPException(status_code=404, detail="Task not found")
    return msg


@router.get("/{task_id}/workroom/messages", response_model=PaginatedMessages)
def list_workroom_messages(
    task_id: str,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedMessages:
    result = svc.list_messages(task_id, page, page_size)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    items, total = result
    return PaginatedMessages(items=items, page=page, page_size=page_size, total=total)


@router.post("/{task_id}/workroom/uploads", response_model=UploadResponse, status_code=201)
async def upload_workroom_file(
    task_id: str,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
    file: UploadFile = File(...),
    category: UploadCategory = Form(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
) -> UploadResponse:
    filename = file.filename or "upload.bin"
    out = svc.add_upload(
        task_id,
        filename=filename,
        category=category,
        title=title,
        description=description,
    )
    if not out:
        raise HTTPException(status_code=404, detail="Task not found")
    return out


@router.delete("/{task_id}/workroom/uploads/{upload_id}", status_code=204)
def delete_workroom_upload(
    task_id: str,
    upload_id: str,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> Response:
    if not svc.delete_upload(task_id, upload_id):
        raise HTTPException(status_code=404, detail="Upload or task not found")
    return Response(status_code=204)


@router.patch("/{task_id}/workroom/checklist/{item_id}")
def patch_checklist_item(
    task_id: str,
    item_id: str,
    body: ChecklistPatchBody,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
):
    item = svc.patch_checklist(task_id, item_id, body)
    if not item:
        raise HTTPException(status_code=404, detail="Task or checklist item not found")
    return item


@router.get("/{task_id}/workroom/templates", response_model=list[WorkroomTemplate])
def workroom_templates(
    task_id: str,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> list[WorkroomTemplate]:
    tpl = svc.templates(task_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return tpl


@router.get("/{task_id}/workroom/links", response_model=list[WorkroomLink])
def workroom_links(
    task_id: str,
    svc: Annotated[ContributorTaskService, Depends(get_contributor_task_service)],
) -> list[WorkroomLink]:
    links = svc.links(task_id)
    if links is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return links

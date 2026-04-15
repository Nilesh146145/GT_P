from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.contributor.schemas.submissions import (
    CreateSubmissionBody,
    PaginatedSubmissions,
    PatchSubmissionBody,
    ResubmitBody,
    ReviewFeedbackResponse,
    SubmissionDetail,
    SubmissionListItem,
    SubmissionMode,
    SubmissionStatus,
    SubmitBody,
)
from app.contributor.dependencies import get_contributor_id
from app.contributor.services.submission_store import (
    SubmissionStore,
    file_refs_for_ids,
    get_submission_store,
)

router = APIRouter(
    prefix="/api/contributor",
    tags=["contributor-submissions"],
    dependencies=[Depends(get_contributor_id)],
)


def _to_detail(rec) -> SubmissionDetail:
    return SubmissionDetail(
        id=rec.id,
        task_id=rec.task_id,
        version=rec.version,
        submitted_at=rec.submitted_at,
        status=rec.status,
        notes=rec.notes,
        files=file_refs_for_ids(rec.file_ids),
        evidence=list(rec.evidence),
        checklist_acknowledgements=list(rec.checklist_acknowledgements),
        review_score=rec.review_score,
        reviewer_feedback=rec.reviewer_feedback,
        rubric_scores=list(rec.rubric_scores),
        structured_responses=list(rec.structured_responses),
    )


@router.get("/submissions", response_model=PaginatedSubmissions)
def list_submissions(
    sub_store: Annotated[SubmissionStore, Depends(get_submission_store)],
    status: SubmissionStatus | None = None,
    task_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    rows, total = sub_store.list_filtered(
        status=status, task_id=task_id, page=page, page_size=page_size
    )
    items = [
        SubmissionListItem(
            id=r.id,
            task_id=r.task_id,
            version=r.version,
            submitted_at=r.submitted_at,
            status=r.status,
        )
        for r in rows
    ]
    return PaginatedSubmissions(
        items=items, page=page, page_size=page_size, total=total
    )


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
def get_submission(
    submission_id: str,
    sub_store: Annotated[SubmissionStore, Depends(get_submission_store)],
):
    rec = sub_store.get(submission_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _to_detail(rec)


@router.post("/tasks/{task_id}/submissions", response_model=SubmissionDetail, status_code=201)
def create_submission(
    task_id: str,
    body: CreateSubmissionBody,
    sub_store: Annotated[SubmissionStore, Depends(get_submission_store)],
):
    mode = body.submission_mode
    if mode == SubmissionMode.draft:
        as_draft = True
    elif mode in (SubmissionMode.submit, SubmissionMode.resubmit):
        as_draft = False
    else:
        raise HTTPException(status_code=400, detail="Invalid submission_mode")

    rec = sub_store.create_for_task(
        task_id,
        version=body.version,
        notes=body.notes,
        file_ids=body.file_ids,
        evidence_items=body.evidence_items,
        structured_responses=body.structured_responses,
        as_draft=as_draft,
    )
    return _to_detail(rec)


def _patch_mutates(body: PatchSubmissionBody) -> bool:
    d = body.model_dump(exclude_unset=True)
    return bool(d)


@router.patch("/submissions/{submission_id}", response_model=SubmissionDetail)
def patch_submission(
    submission_id: str,
    body: PatchSubmissionBody,
    sub_store: Annotated[SubmissionStore, Depends(get_submission_store)],
):
    rec = sub_store.get(submission_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if _patch_mutates(body) and not sub_store.is_editable(rec):
        raise HTTPException(
            status_code=403,
            detail=(
                "Submission cannot be edited after submit unless rework is required."
            ),
        )
    rec = sub_store.update(
        submission_id,
        version=body.version,
        notes=body.notes,
        file_ids=body.file_ids,
        evidence_items=body.evidence_items,
        structured_responses=body.structured_responses,
        checklist_acknowledgements=body.checklist_acknowledgements,
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _to_detail(rec)


@router.post("/submissions/{submission_id}/submit", response_model=SubmissionDetail)
def submit_submission(
    submission_id: str,
    body: SubmitBody,
    sub_store: Annotated[SubmissionStore, Depends(get_submission_store)],
):
    rec = sub_store.submit(
        submission_id,
        notes=body.notes,
        confirm_checklist_complete=body.confirm_checklist_complete,
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _to_detail(rec)


@router.post("/submissions/{submission_id}/resubmit", response_model=SubmissionDetail)
def resubmit_submission(
    submission_id: str,
    body: ResubmitBody,
    sub_store: Annotated[SubmissionStore, Depends(get_submission_store)],
):
    rec = sub_store.resubmit(
        submission_id,
        notes=body.notes,
        file_ids=body.file_ids,
        evidence_items=body.evidence_items,
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _to_detail(rec)


@router.get("/tasks/{task_id}/latest-submission", response_model=SubmissionDetail)
def latest_submission(
    task_id: str,
    sub_store: Annotated[SubmissionStore, Depends(get_submission_store)],
):
    rec = sub_store.latest_for_task(task_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="No submission for this task")
    return _to_detail(rec)


@router.get("/tasks/{task_id}/review-feedback", response_model=ReviewFeedbackResponse)
def review_feedback(
    task_id: str,
    sub_store: Annotated[SubmissionStore, Depends(get_submission_store)],
):
    rec = sub_store.latest_for_task(task_id)
    if rec is None:
        return ReviewFeedbackResponse(
            task_id=task_id,
            submission_id=None,
            reviewer_feedback=None,
            review_score=None,
            rubric_scores=[],
        )
    return ReviewFeedbackResponse(
        task_id=task_id,
        submission_id=rec.id,
        reviewer_feedback=rec.reviewer_feedback,
        review_score=rec.review_score,
        rubric_scores=list(rec.rubric_scores) if rec.rubric_scores else [],
    )

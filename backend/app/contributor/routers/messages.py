from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.contributor.schemas.messages import (
    MessageCreate,
    MessageInThread,
    MessageRatingBody,
    ThreadDetail,
    ThreadListResponse,
    ThreadRoleFilter,
)
from app.contributor.dependencies import get_contributor_id
from app.contributor.services.messages_store import store

router = APIRouter(
    prefix="/api/contributor/messages",
    tags=["contributor-messages"],
    dependencies=[Depends(get_contributor_id)],
)


@router.get("/threads", response_model=ThreadListResponse)
def list_threads(
    role: ThreadRoleFilter = Query(default=ThreadRoleFilter.all),
    q: str | None = Query(default=None, description="Search last message / project name"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ThreadListResponse:
    items, total = store.list_threads(role.value, q, page, page_size)
    return ThreadListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
def get_thread(thread_id: str) -> ThreadDetail:
    th = store.get_thread(thread_id)
    if not th:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return store.thread_to_detail(th)


@router.post(
    "/threads/{thread_id}/messages",
    response_model=MessageInThread,
    status_code=status.HTTP_201_CREATED,
)
def post_message(thread_id: str, body: MessageCreate) -> MessageInThread:
    msg = store.add_message(thread_id, body.content, body.attachment_ids)
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return MessageInThread(
        id=msg.id,
        sender_id=msg.sender_id,
        sender_name=msg.sender_name,
        sender_role=msg.sender_role,
        content=msg.content,
        timestamp=msg.timestamp,
        attachment_ids=msg.attachment_ids,
        rating=msg.rating,
    )


@router.post(
    "/threads/{thread_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def mark_thread_read(thread_id: str) -> Response:
    ok = store.mark_read(thread_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{message_id}/rating",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def rate_message(message_id: str, body: MessageRatingBody) -> Response:
    ok = store.set_message_rating(message_id, body.rating.value)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

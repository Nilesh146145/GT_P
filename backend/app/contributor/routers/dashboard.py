"""Dashboard module routes: contributor home, header profile strip, notifications."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.contributor.schemas.dashboard import (
    ContributorDashboard,
    ContributorMe,
    NotificationItem,
    NotificationReadPatch,
    NotificationsListResponse,
    ReadAllResponse,
)
from app.contributor.dependencies import get_contributor_id
from app.contributor.services import dashboard_store as dash

router = APIRouter(
    prefix="/api/contributor",
    tags=["contributor-dashboard"],
    dependencies=[Depends(get_contributor_id)],
)


@router.get("/me", response_model=ContributorMe)
def get_me(contributor_id: Annotated[str, Depends(get_contributor_id)]) -> ContributorMe:
    me = dash.get_contributor_me()
    return me.model_copy(update={"id": contributor_id})


@router.get("/dashboard", response_model=ContributorDashboard)
def get_dashboard(include: str | None = Query(default=None, description="Comma-separated sections")) -> ContributorDashboard:
    return dash.get_dashboard(include)


@router.get("/notifications", response_model=NotificationsListResponse)
def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    read: bool | None = Query(default=None),
    type: str | None = Query(default=None, alias="type"),
) -> NotificationsListResponse:
    items, total = dash.list_notifications_filtered(
        page=page,
        page_size=page_size,
        read=read,
        type_=type,
    )
    return NotificationsListResponse(items=items, page=page, page_size=page_size, total=total)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationItem)
def patch_notification_read(notification_id: str, body: NotificationReadPatch) -> NotificationItem:
    ok = dash.set_notification_read(notification_id, body.read)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    n = dash.get_notification_by_id(notification_id)
    assert n is not None
    return n


@router.post("/notifications/read-all", response_model=ReadAllResponse)
def read_all_notifications() -> ReadAllResponse:
    updated = dash.mark_all_notifications_read()
    return ReadAllResponse(updated=updated)

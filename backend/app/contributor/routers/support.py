"""Contributor support hub: FAQs, tickets, grievances, safety reports."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.contributor.schemas.support import (
    FAQListResponse,
    GrievanceCreate,
    GrievanceDetail,
    GrievanceListResponse,
    PaginatedTickets,
    SafetyReportCreate,
    SafetyReportResponse,
    TicketCategory,
    TicketCreate,
    TicketDetail,
    TicketMessage,
    TicketMessageCreate,
    TicketPriority,
    TicketStatus,
)
from app.contributor.dependencies import get_contributor_id
from app.contributor.services.support_store import store

router = APIRouter(
    prefix="/api/contributor/support",
    tags=["contributor-support"],
    dependencies=[Depends(get_contributor_id)],
)


@router.get("/faqs", response_model=FAQListResponse)
def list_faqs(
    category: str | None = Query(default=None, description="Filter by FAQ category slug"),
    q: str | None = Query(default=None, description="Search question and answer text"),
) -> FAQListResponse:
    items, total = store.list_faqs(category, q)
    return FAQListResponse(items=items, total=total)


@router.get("/tickets", response_model=PaginatedTickets)
def list_tickets(
    status: TicketStatus | None = Query(default=None),
    priority: TicketPriority | None = Query(default=None),
    category: TicketCategory | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedTickets:
    items, total = store.list_tickets(
        status=status,
        priority=priority,
        category=category,
        page=page,
        page_size=page_size,
    )
    return PaginatedTickets(items=items, page=page, page_size=page_size, total=total)


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: str) -> TicketDetail:
    d = store.get_ticket(ticket_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return d


@router.post("/tickets", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
def create_ticket(body: TicketCreate) -> TicketDetail:
    return store.create_ticket(body.model_dump())


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=TicketMessage,
    status_code=status.HTTP_201_CREATED,
)
def post_ticket_message(ticket_id: str, body: TicketMessageCreate) -> TicketMessage:
    msg = store.add_ticket_message(ticket_id, body.message, body.attachment_ids)
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return msg


@router.post("/grievances", response_model=GrievanceDetail, status_code=status.HTTP_201_CREATED)
def create_grievance(body: GrievanceCreate) -> GrievanceDetail:
    return store.create_grievance(body.model_dump())


@router.get("/grievances", response_model=GrievanceListResponse)
def list_grievances() -> GrievanceListResponse:
    items, total = store.list_grievances()
    return GrievanceListResponse(items=items, total=total)


@router.get("/grievances/{grievance_id}", response_model=GrievanceDetail)
def get_grievance(grievance_id: str) -> GrievanceDetail:
    d = store.get_grievance(grievance_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grievance not found")
    return d


@router.post("/safety-reports", response_model=SafetyReportResponse, status_code=status.HTTP_201_CREATED)
def create_safety_report(body: SafetyReportCreate) -> SafetyReportResponse:
    row = store.create_safety_report(body.model_dump())
    return SafetyReportResponse(
        id=row["id"],
        category=row["category"],
        description=row["description"],
        related_reference=row.get("related_reference"),
        attachment_ids=list(row.get("attachment_ids", [])),
        status=row["status"],
        created_at=row["created_at"],
    )

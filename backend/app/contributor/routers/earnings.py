from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.contributor.schemas.earnings import ChartPeriod, EarningSortBy
from app.contributor.dependencies import get_contributor_id
from app.contributor.services.earnings_data import contributor_data

router = APIRouter(
    prefix="/api/contributor/earnings",
    tags=["earnings"],
    dependencies=[Depends(get_contributor_id)],
)


@router.get("/summary")
def get_earnings_summary():
    return contributor_data.summary()


@router.get("/overview")
def get_earnings_overview():
    return contributor_data.overview()


@router.get("/chart")
def get_earnings_chart(
    period: ChartPeriod = Query(default=ChartPeriod.THREE_MONTHS, description="3m, 6m, or 1y"),
):
    return contributor_data.chart(period)


@router.get("")
def list_earnings(
    status: Optional[str] = Query(default=None),
    sort_by: EarningSortBy = Query(default=EarningSortBy.DATE),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return contributor_data.list_earnings(
        status=status,
        sort_by=sort_by.value,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get("/kyc/status")
def get_kyc_status():
    return contributor_data.kyc_status()


@router.post("/kyc/start")
def start_kyc():
    return contributor_data.start_kyc()


@router.get("/{earning_id}")
def get_earning(earning_id: str):
    detail = contributor_data.earning_detail(earning_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Earning not found")
    return detail

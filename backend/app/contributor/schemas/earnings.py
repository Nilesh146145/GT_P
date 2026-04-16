from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class ChartPeriod(str, Enum):
    THREE_MONTHS = "3m"
    SIX_MONTHS = "6m"
    ONE_YEAR = "1y"


class EarningSortBy(str, Enum):
    TASK = "task"
    AMOUNT = "amount"
    STATUS = "status"
    DATE = "date"


class KycBannerLevel(str, Enum):
    APPROACHING = "approaching"
    THRESHOLD_REACHED = "threshold_reached"


class KycStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    APPROACHING = "approaching"
    REQUIRED = "required"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    REJECTED = "rejected"


class LedgerStatus(str, Enum):
    EARNED = "earned"
    PROCESSING = "processing"
    PAID = "paid"
    ON_HOLD = "on_hold"


class EarningSummary(BaseModel):
    total_earned: Decimal
    eligible: Decimal
    pending: Decimal
    processing: Decimal
    paid_out: Decimal
    currency: str
    current_month: Decimal
    previous_month: Decimal
    lifetime_tasks_completed: int
    average_per_task: Decimal
    on_hold: Decimal = Decimal("0.00")


class KycBanner(BaseModel):
    level: KycBannerLevel
    message: str
    cta_text: str
    cta_url: str


class EarningsOverview(BaseModel):
    page_title: str = "Earnings & Payouts"
    sub_label: str = "Your task earnings, payment history, and payout status."
    earned_this_month: Decimal
    total_paid_all_time: Decimal
    pending_payout: Decimal
    on_hold: Decimal
    currency: str
    kyc_status: KycStatus
    kyc_banner: Optional[KycBanner] = None


class ChartDataPoint(BaseModel):
    period_label: str
    amount: Decimal
    tasks_count: int = 0


class EarningChartResponse(BaseModel):
    period: ChartPeriod
    currency: str
    data: List[ChartDataPoint]


class EarningListItem(BaseModel):
    id: str
    task_id: str
    task_title: str
    project_title: str
    amount: Decimal
    currency: str
    status: str
    acceptance_date: date
    earned_at: datetime
    paid_at: Optional[datetime] = None
    estimated_eligible_date: Optional[date] = None
    expected_payment_date: Optional[date] = None
    payment_reference: Optional[str] = None
    payout_id: Optional[str] = None


class PaginatedEarnings(BaseModel):
    items: List[EarningListItem]
    page: int
    page_size: int
    total: int


class TaskPricing(BaseModel):
    unit: str = "hour"
    rate: Decimal
    currency: str


class EarningDetail(BaseModel):
    id: str
    task_id: str
    task_title: str
    project_title: str
    gross_amount: Decimal
    platform_fee: Decimal
    tax_withholding: Decimal
    net_amount: Decimal
    task_pricing: TaskPricing
    estimated_hours: Optional[Decimal] = None
    status: str
    acceptance_date: date
    earned_at: datetime
    paid_at: Optional[datetime] = None
    expected_payment_date: Optional[date] = None
    payment_reference: Optional[str] = None
    payout_ref: Optional[str] = None
    currency: str


class KycStatusResponse(BaseModel):
    status: KycStatus
    threshold_amount: Decimal
    current_eligible_amount: Decimal
    currency: str
    payouts_paused: bool
    support_url: Optional[str] = None
    message: Optional[str] = None

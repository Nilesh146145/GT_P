from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.contributor.schemas.earnings import (
    ChartDataPoint,
    ChartPeriod,
    EarningsOverview,
    EarningChartResponse,
    EarningDetail,
    EarningListItem,
    EarningSummary,
    KycBanner,
    KycBannerLevel,
    KycStatus,
    KycStatusResponse,
    LedgerStatus,
    PaginatedEarnings,
    TaskPricing,
)
from app.contributor.schemas.payouts import IncludedEarning, PaginatedPayouts, PayoutDetail, PayoutListItem
from app.contributor.schemas.preferences import PayoutPreferences, PayoutPreferencesUpdate, PreferredMethod

UTC = timezone.utc


def _dt(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


MOCK_EARNINGS: List[Dict[str, Any]] = [
    {
        "id": "ern_001",
        "task_id": "tsk_a1",
        "task_title": "Label dataset batch 12",
        "project_title": "Vision QA",
        "amount": Decimal("120.00"),
        "currency": "USD",
        "status": "paid",
        "ledger_status": "paid",
        "earned_at": _dt(2026, 3, 10, 14, 30),
        "acceptance_date": date(2026, 3, 10),
        "paid_at": _dt(2026, 3, 15, 9, 0),
        "estimated_eligible_date": None,
        "expected_payment_date": None,
        "payment_reference": "PO-2026-0001",
        "payout_id": "po_001",
        "gross_amount": Decimal("125.00"),
        "platform_fee": Decimal("5.00"),
        "tax_withholding": Decimal("0.00"),
        "net_amount": Decimal("120.00"),
        "task_pricing": {"unit": "hour", "rate": Decimal("25.00"), "currency": "USD"},
        "estimated_hours": Decimal("5.0"),
        "payout_ref": "PO-2026-0001",
    },
    {
        "id": "ern_002",
        "task_id": "tsk_b2",
        "task_title": "Review annotations",
        "project_title": "NLP Assist",
        "amount": Decimal("85.50"),
        "currency": "USD",
        "status": "eligible",
        "ledger_status": "earned",
        "earned_at": _dt(2026, 3, 28, 11, 0),
        "acceptance_date": date(2026, 3, 28),
        "paid_at": None,
        "estimated_eligible_date": date(2026, 4, 5),
        "expected_payment_date": date(2026, 4, 9),
        "payment_reference": None,
        "payout_id": None,
        "gross_amount": Decimal("90.00"),
        "platform_fee": Decimal("4.50"),
        "tax_withholding": Decimal("0.00"),
        "net_amount": Decimal("85.50"),
        "task_pricing": {"unit": "hour", "rate": Decimal("30.00"), "currency": "USD"},
        "estimated_hours": Decimal("3.0"),
        "payout_ref": None,
    },
    {
        "id": "ern_003",
        "task_id": "tsk_c3",
        "task_title": "Audio transcription QC",
        "project_title": "Speech",
        "amount": Decimal("44.00"),
        "currency": "USD",
        "status": "pending",
        "ledger_status": "earned",
        "earned_at": _dt(2026, 4, 1, 16, 45),
        "acceptance_date": date(2026, 4, 1),
        "paid_at": None,
        "estimated_eligible_date": date(2026, 4, 10),
        "expected_payment_date": date(2026, 4, 14),
        "payment_reference": None,
        "payout_id": None,
        "gross_amount": Decimal("46.32"),
        "platform_fee": Decimal("2.32"),
        "tax_withholding": Decimal("0.00"),
        "net_amount": Decimal("44.00"),
        "task_pricing": {"unit": "hour", "rate": Decimal("22.00"), "currency": "USD"},
        "estimated_hours": Decimal("2.0"),
        "payout_ref": None,
    },
    {
        "id": "ern_004",
        "task_id": "tsk_d4",
        "task_title": "Edge case tagging",
        "project_title": "Vision QA",
        "amount": Decimal("200.00"),
        "currency": "USD",
        "status": "processing",
        "ledger_status": "on_hold",
        "earned_at": _dt(2026, 4, 2, 10, 0),
        "acceptance_date": date(2026, 4, 2),
        "paid_at": None,
        "estimated_eligible_date": date(2026, 4, 8),
        "expected_payment_date": date(2026, 4, 16),
        "payment_reference": None,
        "payout_id": "po_002",
        "gross_amount": Decimal("210.53"),
        "platform_fee": Decimal("10.53"),
        "tax_withholding": Decimal("0.00"),
        "net_amount": Decimal("200.00"),
        "task_pricing": {"unit": "hour", "rate": Decimal("40.00"), "currency": "USD"},
        "estimated_hours": Decimal("5.0"),
        "payout_ref": None,
    },
]

MOCK_PAYOUTS: List[Dict[str, Any]] = [
    {
        "id": "po_001",
        "reference": "PO-2026-0001",
        "amount": Decimal("120.00"),
        "currency": "USD",
        "method": "bank_transfer",
        "status": "completed",
        "initiated_at": _dt(2026, 3, 14, 12, 0),
        "completed_at": _dt(2026, 3, 15, 9, 0),
        "bank_last4": "4242",
        "earning_ids": ["ern_001"],
        "included_earnings": [
            {
                "earning_id": "ern_001",
                "task_title": "Label dataset batch 12",
                "amount": Decimal("120.00"),
                "currency": "USD",
            }
        ],
    },
    {
        "id": "po_002",
        "reference": "PO-2026-0002",
        "amount": Decimal("200.00"),
        "currency": "USD",
        "method": "bank_transfer",
        "status": "processing",
        "initiated_at": _dt(2026, 4, 3, 8, 0),
        "completed_at": None,
        "bank_last4": "4242",
        "earning_ids": ["ern_004"],
        "included_earnings": [
            {
                "earning_id": "ern_004",
                "task_title": "Edge case tagging",
                "amount": Decimal("200.00"),
                "currency": "USD",
            }
        ],
    },
]

PAYOUT_PREFERENCES: Dict[str, Any] = {
    "preferred_method": PreferredMethod.BANK_TRANSFER,
    "minimum_payout_amount": Decimal("50.00"),
    "auto_payout": True,
    "account_name": "Jane Contributor",
    "account_number": "****7890",
    "bank_name": "Example Bank",
    "routing_code": "021000021",
    "country": "US",
    "provider": None,
    "phone_number": None,
    "paypal_email": None,
    "upi_id": None,
    "wallet_address": None,
    "network": None,
    "token": None,
}

KYC_STATE: Dict[str, Any] = {
    "status": KycStatus.REQUIRED,
    "threshold_amount": Decimal("150.00"),
    "support_url": "https://support.example.com/kyc",
}

# Chart series keyed by period
CHART_DATA: Dict[str, List[Dict[str, Any]]] = {
    "3m": [
        {"period_label": "2026-01", "amount": Decimal("410.00"), "tasks_count": 6},
        {"period_label": "2026-02", "amount": Decimal("355.25"), "tasks_count": 5},
        {"period_label": "2026-03", "amount": Decimal("520.80"), "tasks_count": 7},
    ],
    "6m": [
        {"period_label": "2025-10", "amount": Decimal("280.00"), "tasks_count": 4},
        {"period_label": "2025-11", "amount": Decimal("310.50"), "tasks_count": 4},
        {"period_label": "2025-12", "amount": Decimal("290.00"), "tasks_count": 4},
        {"period_label": "2026-01", "amount": Decimal("410.00"), "tasks_count": 6},
        {"period_label": "2026-02", "amount": Decimal("355.25"), "tasks_count": 5},
        {"period_label": "2026-03", "amount": Decimal("520.80"), "tasks_count": 7},
    ],
    "1y": [
        {"period_label": "2025-Q2", "amount": Decimal("890.00"), "tasks_count": 12},
        {"period_label": "2025-Q3", "amount": Decimal("1020.50"), "tasks_count": 14},
        {"period_label": "2025-Q4", "amount": Decimal("980.00"), "tasks_count": 13},
        {"period_label": "2026-Q1", "amount": Decimal("1286.05"), "tasks_count": 16},
    ],
}


class ContributorData:
    def _ledger_status(self, earning: Dict[str, Any]) -> str:
        return earning.get("ledger_status", earning["status"])

    def _on_hold_amount(self) -> Decimal:
        return sum(
            e["amount"] for e in MOCK_EARNINGS if self._ledger_status(e) == LedgerStatus.ON_HOLD.value
        )

    def _pending_payout_amount(self) -> Decimal:
        return sum(
            e["amount"]
            for e in MOCK_EARNINGS
            if self._ledger_status(e) in (LedgerStatus.EARNED.value, LedgerStatus.PROCESSING.value)
        )

    def _kyc_banner(self) -> Optional[KycBanner]:
        status = KYC_STATE["status"]
        if status == KycStatus.APPROACHING:
            return KycBanner(
                level=KycBannerLevel.APPROACHING,
                message="Earnings approaching KYC threshold. Start KYC to avoid delays.",
                cta_text="Start KYC",
                cta_url="/kyc/start",
            )
        if status in (KycStatus.REQUIRED, KycStatus.REJECTED):
            return KycBanner(
                level=KycBannerLevel.THRESHOLD_REACHED,
                message="Payouts paused until KYC complete.",
                cta_text="Complete KYC",
                cta_url="/kyc/start",
            )
        return None

    def summary(self) -> EarningSummary:
        total = sum(e["amount"] for e in MOCK_EARNINGS)
        eligible = sum(e["amount"] for e in MOCK_EARNINGS if e["status"] == "eligible")
        pending = sum(e["amount"] for e in MOCK_EARNINGS if e["status"] == "pending")
        processing = sum(e["amount"] for e in MOCK_EARNINGS if e["status"] == "processing")
        paid_out = sum(e["amount"] for e in MOCK_EARNINGS if e["status"] == "paid")
        now = datetime.now(UTC)
        cm_start = date(now.year, now.month, 1)
        if now.month == 1:
            pm_start = date(now.year - 1, 12, 1)
        else:
            pm_start = date(now.year, now.month - 1, 1)

        def in_month(earned: datetime, start: date) -> bool:
            d = earned.date()
            if d.month != start.month or d.year != start.year:
                return False
            return True

        current_month = sum(
            e["amount"] for e in MOCK_EARNINGS if in_month(e["earned_at"], cm_start)
        )
        previous_month = sum(
            e["amount"] for e in MOCK_EARNINGS if in_month(e["earned_at"], pm_start)
        )
        n = len(MOCK_EARNINGS)
        avg = (total / n) if n else Decimal("0")
        return EarningSummary(
            total_earned=total,
            eligible=eligible,
            pending=pending,
            processing=processing,
            paid_out=paid_out,
            currency="USD",
            current_month=current_month,
            previous_month=previous_month,
            lifetime_tasks_completed=n,
            average_per_task=avg.quantize(Decimal("0.01")),
            on_hold=self._on_hold_amount(),
        )

    def overview(self) -> EarningsOverview:
        summary = self.summary()
        return EarningsOverview(
            earned_this_month=summary.current_month,
            total_paid_all_time=summary.paid_out,
            pending_payout=self._pending_payout_amount(),
            on_hold=self._on_hold_amount(),
            currency=summary.currency,
            kyc_status=KYC_STATE["status"],
            kyc_banner=self._kyc_banner(),
        )

    def chart(self, period: ChartPeriod) -> EarningChartResponse:
        key = period.value
        rows = CHART_DATA.get(key, CHART_DATA["3m"])
        return EarningChartResponse(
            period=period,
            currency="USD",
            data=[ChartDataPoint(**r) for r in rows],
        )

    def list_earnings(
        self,
        status: Optional[str],
        sort_by: str,
        sort_dir: str,
        page: int,
        page_size: int,
    ) -> PaginatedEarnings:
        items = list(MOCK_EARNINGS)
        if status:
            items = [e for e in items if e["status"] == status]
        reverse = sort_dir.lower() == "desc"

        def sort_key(e: Dict[str, Any]) -> Any:
            if sort_by == "task":
                return e["task_title"].lower()
            if sort_by == "amount":
                return e["amount"]
            if sort_by == "status":
                return e["status"]
            return e["earned_at"]

        items.sort(key=sort_key, reverse=reverse)
        total = len(items)
        start = (page - 1) * page_size
        slice_ = items[start : start + page_size]
        return PaginatedEarnings(
            items=[
                EarningListItem(
                    id=e["id"],
                    task_id=e["task_id"],
                    task_title=e["task_title"],
                    project_title=e["project_title"],
                    amount=e["amount"],
                    currency=e["currency"],
                    status=self._ledger_status(e),
                    acceptance_date=e["acceptance_date"],
                    earned_at=e["earned_at"],
                    paid_at=e.get("paid_at"),
                    estimated_eligible_date=e.get("estimated_eligible_date"),
                    expected_payment_date=e.get("expected_payment_date"),
                    payment_reference=e.get("payment_reference"),
                    payout_id=e.get("payout_id"),
                )
                for e in slice_
            ],
            page=page,
            page_size=page_size,
            total=total,
        )

    def earning_detail(self, earning_id: str) -> Optional[EarningDetail]:
        for e in MOCK_EARNINGS:
            if e["id"] == earning_id:
                tp = e["task_pricing"]
                return EarningDetail(
                    id=e["id"],
                    task_id=e["task_id"],
                    task_title=e["task_title"],
                    project_title=e["project_title"],
                    gross_amount=e["gross_amount"],
                    platform_fee=e["platform_fee"],
                    tax_withholding=e["tax_withholding"],
                    net_amount=e["net_amount"],
                    task_pricing=TaskPricing(**tp),
                    estimated_hours=e.get("estimated_hours"),
                    status=self._ledger_status(e),
                    acceptance_date=e["acceptance_date"],
                    earned_at=e["earned_at"],
                    paid_at=e.get("paid_at"),
                    expected_payment_date=e.get("expected_payment_date"),
                    payment_reference=e.get("payment_reference"),
                    payout_ref=e.get("payout_ref"),
                    currency=e["currency"],
                )
        return None

    def kyc_status(self) -> KycStatusResponse:
        eligible_amount = sum(
            e["amount"] for e in MOCK_EARNINGS if self._ledger_status(e) != LedgerStatus.PAID.value
        )
        status = KYC_STATE["status"]
        paused = status in (KycStatus.REQUIRED, KycStatus.IN_PROGRESS, KycStatus.REJECTED)
        message = None
        if status == KycStatus.REQUIRED:
            message = (
                f"Identity verification required. Payouts above "
                f"${KYC_STATE['threshold_amount']} are paused."
            )
        elif status == KycStatus.VERIFIED:
            message = "Identity verified. Held payouts are released to normal processing."
        elif status == KycStatus.REJECTED:
            message = "Identity verification unsuccessful. Please try again with a different document."

        return KycStatusResponse(
            status=status,
            threshold_amount=KYC_STATE["threshold_amount"],
            current_eligible_amount=eligible_amount,
            currency="USD",
            payouts_paused=paused,
            support_url=KYC_STATE["support_url"],
            message=message,
        )

    def start_kyc(self) -> Dict[str, str]:
        KYC_STATE["status"] = KycStatus.IN_PROGRESS
        return {
            "status": "in_progress",
            "redirect_url": "https://kyc.vendor.example/start-session",
            "message": "Redirect to KYC vendor initiated.",
        }

    def list_payouts(
        self,
        status: Optional[str],
        sort_by: str,
        sort_dir: str,
        page: int,
        page_size: int,
    ) -> PaginatedPayouts:
        items = list(MOCK_PAYOUTS)
        if status:
            items = [p for p in items if p["status"] == status]
        reverse = sort_dir.lower() == "desc"

        def sort_key(p: Dict[str, Any]) -> Any:
            if sort_by == "reference":
                return p["reference"].lower()
            if sort_by == "amount":
                return p["amount"]
            if sort_by == "method":
                return p["method"]
            if sort_by == "status":
                return p["status"]
            return p["initiated_at"]

        items.sort(key=sort_key, reverse=reverse)
        total = len(items)
        start = (page - 1) * page_size
        slice_ = items[start : start + page_size]
        return PaginatedPayouts(
            items=[
                PayoutListItem(
                    id=p["id"],
                    reference=p["reference"],
                    amount=p["amount"],
                    currency=p["currency"],
                    method=p["method"],
                    status=p["status"],
                    initiated_at=p["initiated_at"],
                    completed_at=p.get("completed_at"),
                    bank_last4=p.get("bank_last4"),
                )
                for p in slice_
            ],
            page=page,
            page_size=page_size,
            total=total,
        )

    def payout_detail(self, payout_id: str) -> Optional[PayoutDetail]:
        for p in MOCK_PAYOUTS:
            if p["id"] == payout_id:
                return PayoutDetail(
                    id=p["id"],
                    reference=p["reference"],
                    amount=p["amount"],
                    currency=p["currency"],
                    method=p["method"],
                    status=p["status"],
                    initiated_at=p["initiated_at"],
                    completed_at=p.get("completed_at"),
                    bank_last4=p.get("bank_last4"),
                    earning_ids=list(p["earning_ids"]),
                    included_earnings=[IncludedEarning(**x) for x in p["included_earnings"]],
                )
        return None

    def get_preferences(self) -> PayoutPreferences:
        return PayoutPreferences(**PAYOUT_PREFERENCES)

    def update_preferences(self, body: PayoutPreferencesUpdate) -> PayoutPreferences:
        data = PAYOUT_PREFERENCES
        update = body.model_dump(exclude_unset=True)
        for k, v in update.items():
            data[k] = v
        return PayoutPreferences(**data)


contributor_data = ContributorData()


def apply_temp_demo_seed() -> None:
    """Idempotent extra ledger rows for API testing and E2E flows."""
    ids = {e["id"] for e in MOCK_EARNINGS}
    if "ern_demo_extra" not in ids:
        MOCK_EARNINGS.append(
            {
                "id": "ern_demo_extra",
                "task_id": "tsk_006",
                "task_title": "Large migration script (over-cap test)",
                "project_title": "Finance",
                "amount": Decimal("95.25"),
                "currency": "USD",
                "status": "eligible",
                "ledger_status": "earned",
                "earned_at": _dt(2026, 4, 5, 9, 0),
                "acceptance_date": date(2026, 4, 5),
                "paid_at": None,
                "estimated_eligible_date": date(2026, 4, 12),
                "expected_payment_date": date(2026, 4, 18),
                "payment_reference": None,
                "payout_id": None,
                "gross_amount": Decimal("100.00"),
                "platform_fee": Decimal("4.75"),
                "tax_withholding": Decimal("0.00"),
                "net_amount": Decimal("95.25"),
                "task_pricing": {"unit": "hour", "rate": Decimal("45.00"), "currency": "USD"},
                "estimated_hours": Decimal("2.5"),
                "payout_ref": None,
            }
        )
    if "ern_004" not in ids:
        MOCK_EARNINGS.append(
            {
                "id": "ern_004",
                "task_id": "tsk_004",
                "task_title": "Design system audit",
                "project_title": "Healthcare",
                "amount": Decimal("200.00"),
                "currency": "EUR",
                "status": "paid",
                "ledger_status": "paid",
                "earned_at": _dt(2026, 3, 20, 10, 0),
                "acceptance_date": date(2026, 3, 20),
                "paid_at": _dt(2026, 3, 25, 8, 0),
                "estimated_eligible_date": None,
                "expected_payment_date": None,
                "payment_reference": "PO-EU-2026-01",
                "payout_id": "po_003",
                "gross_amount": Decimal("210.00"),
                "platform_fee": Decimal("10.00"),
                "tax_withholding": Decimal("0.00"),
                "net_amount": Decimal("200.00"),
                "task_pricing": {"unit": "hour", "rate": Decimal("95.00"), "currency": "EUR"},
                "estimated_hours": Decimal("10.0"),
                "payout_ref": "PO-EU-2026-01",
            }
        )
    pids = {p["id"] for p in MOCK_PAYOUTS}
    if "po_003" not in pids:
        MOCK_PAYOUTS.append(
            {
                "id": "po_003",
                "reference": "PO-EU-2026-01",
                "amount": Decimal("200.00"),
                "currency": "EUR",
                "method": "paypal",
                "status": "completed",
                "initiated_at": _dt(2026, 3, 24, 15, 0),
                "completed_at": _dt(2026, 3, 25, 8, 0),
                "bank_last4": None,
                "earning_ids": ["ern_004"],
                "included_earnings": [
                    {
                        "earning_id": "ern_004",
                        "task_title": "Design system audit",
                        "amount": Decimal("200.00"),
                        "currency": "EUR",
                    }
                ],
            }
        )

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import random
import string

from app.project_portfolio.schemas.escalation import EscalationCreate
from app.project_portfolio.schemas.payment import (
    HoldPaymentResponse,
    PaymentHistoryItem,
    PaymentHistoryResponse,
    PendingPaymentItem,
    PendingPaymentsResponse,
    ReleasePaymentResponse,
    SendOtpResponse,
)
from app.project_portfolio.services.escalations import raise_escalation
from app.project_portfolio.services.projects import project_exists


@dataclass
class _PaymentRow:
    id: str
    project_id: str
    task_id: str
    task_title: str
    evidence_id: str
    evidence_title: str
    amount_cents: int
    currency: str
    approved_at: datetime
    state: str
    released_at: datetime | None = None
    otp_code: str | None = None
    otp_expires: datetime | None = None


_PAYMENT_ROWS: list[_PaymentRow] = [
    _PaymentRow(
        id="pay_p1_01",
        project_id="proj_001",
        task_id="tk_proj_001_t1",
        task_title="Wireframes",
        evidence_id="ep_p1_01",
        evidence_title="Brand guidelines PDF",
        amount_cents=25000,
        currency="USD",
        approved_at=datetime(2026, 3, 6, 15, 0, tzinfo=UTC),
        state="pending_release",
    ),
    _PaymentRow(
        id="pay_p1_02",
        project_id="proj_001",
        task_id="tk_proj_001_t2",
        task_title="UI sign-off",
        evidence_id="ep_p1_02",
        evidence_title="Design review notes",
        amount_cents=18000,
        currency="USD",
        approved_at=datetime(2026, 3, 14, 11, 0, tzinfo=UTC),
        state="pending_release",
    ),
    _PaymentRow(
        id="pay_p2_01",
        project_id="proj_002",
        task_id="tk_proj_002_t1",
        task_title="Ingest job",
        evidence_id="ep_p2_01",
        evidence_title="Schema diagram",
        amount_cents=42000,
        currency="USD",
        approved_at=datetime(2026, 3, 20, 9, 30, tzinfo=UTC),
        state="pending_release",
    ),
    _PaymentRow(
        id="pay_p1_hist_01",
        project_id="proj_001",
        task_id="tk_proj_001_t0",
        task_title="Kickoff deck",
        evidence_id="ep_p1_01",
        evidence_title="Brand guidelines PDF",
        amount_cents=5000,
        currency="USD",
        approved_at=datetime(2026, 2, 15, 10, 0, tzinfo=UTC),
        state="released",
        released_at=datetime(2026, 3, 1, 16, 0, tzinfo=UTC),
    ),
]


def _get_payment(payment_id: str) -> _PaymentRow | None:
    for payment in _PAYMENT_ROWS:
        if payment.id == payment_id:
            return payment
    return None


def _belongs(row: _PaymentRow, project_id: str) -> bool:
    return row.project_id == project_id


def list_pending_payments(project_id: str) -> PendingPaymentsResponse | None:
    if not project_exists(project_id):
        return None
    pending: list[PendingPaymentItem] = []
    for payment in _PAYMENT_ROWS:
        if not _belongs(payment, project_id):
            continue
        if payment.state != "pending_release":
            continue
        pending.append(
            PendingPaymentItem(
                payment_id=payment.id,
                task_id=payment.task_id,
                task_title=payment.task_title,
                evidence_id=payment.evidence_id,
                evidence_title=payment.evidence_title,
                amount_cents=payment.amount_cents,
                currency=payment.currency,
                approved_at=payment.approved_at,
            ),
        )
    return PendingPaymentsResponse(project_id=project_id, pending=pending)


def list_payment_history(project_id: str) -> PaymentHistoryResponse | None:
    if not project_exists(project_id):
        return None
    items: list[PaymentHistoryItem] = []
    for payment in _PAYMENT_ROWS:
        if not _belongs(payment, project_id):
            continue
        if payment.state != "released" or payment.released_at is None:
            continue
        items.append(
            PaymentHistoryItem(
                payment_id=payment.id,
                task_id=payment.task_id,
                task_title=payment.task_title,
                evidence_id=payment.evidence_id,
                amount_cents=payment.amount_cents,
                currency=payment.currency,
                released_at=payment.released_at,
            ),
        )
    items.sort(key=lambda x: x.released_at, reverse=True)
    return PaymentHistoryResponse(project_id=project_id, payments=items)


def send_payment_otp(project_id: str, payment_id: str) -> tuple[SendOtpResponse | None, str | None]:
    if not project_exists(project_id):
        return None, "project_not_found"
    payment = _get_payment(payment_id)
    if payment is None or not _belongs(payment, project_id):
        return None, "payment_not_found"
    if payment.state != "pending_release":
        return None, "invalid_state"

    code = "".join(random.choices(string.digits, k=6))
    expires = datetime.now(tz=UTC) + timedelta(minutes=10)
    payment.otp_code = code
    payment.otp_expires = expires
    return (
        SendOtpResponse(
            payment_id=payment_id,
            otp_sent=True,
            expires_at=expires,
            message="OTP sent to authorized approver (demo: use demo_otp to release).",
            demo_otp=code,
        ),
        None,
    )


def release_payment(
    project_id: str,
    payment_id: str,
    *,
    otp: str,
) -> tuple[ReleasePaymentResponse | None, str | None]:
    if not otp.strip():
        return None, "otp_required"
    if not project_exists(project_id):
        return None, "project_not_found"
    payment = _get_payment(payment_id)
    if payment is None or not _belongs(payment, project_id):
        return None, "payment_not_found"
    if payment.state != "pending_release":
        return None, "invalid_state"
    if not payment.otp_code or not payment.otp_expires:
        return None, "otp_invalid"
    if datetime.now(tz=UTC) > payment.otp_expires:
        return None, "otp_expired"
    if otp.strip() != payment.otp_code:
        return None, "otp_invalid"

    now = datetime.now(tz=UTC)
    payment.state = "released"
    payment.released_at = now
    payment.otp_code = None
    payment.otp_expires = None
    return ReleasePaymentResponse(payment_id=payment_id, released_at=now), None


def hold_payment(
    project_id: str,
    payment_id: str,
    *,
    note: str | None,
) -> tuple[HoldPaymentResponse | None, str | None]:
    if not project_exists(project_id):
        return None, "project_not_found"
    payment = _get_payment(payment_id)
    if payment is None or not _belongs(payment, project_id):
        return None, "payment_not_found"
    if payment.state != "pending_release":
        return None, "invalid_state"

    reason_parts = [
        f"Payment hold: {payment_id} for project {project_id}",
        f"Task {payment.task_title} ({payment.task_id}).",
    ]
    if note:
        reason_parts.append(note.strip())
    reason = " ".join(reason_parts)

    body = EscalationCreate(
        project_id=project_id,
        reason=reason,
        severity="payment_hold",
        rework_request_id=None,
    )
    record, err = raise_escalation(body)
    if err or record is None:
        return None, "escalation_failed"

    payment.state = "held"
    payment.otp_code = None
    payment.otp_expires = None

    return HoldPaymentResponse(payment_id=payment_id, escalation_id=record.id), None

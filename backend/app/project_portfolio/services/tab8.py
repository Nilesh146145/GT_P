from __future__ import annotations

import itertools
import random
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # Python 3.9 (datetime.UTC is 3.11+)

from app.project_portfolio.schemas.tab8 import (
    CommercialSummaryResponse,
    M2ConfirmResponse,
    M2ReleaseResponse,
    MilestonePaymentLine,
    SendOtpResponse,
    UatConfirmResponse,
    UatSignoffResponse,
)
from app.project_portfolio.services.projects import project_exists

_UTC = UTC  # alias for readability in this module
_OTP_TTL = timedelta(minutes=15)
_ALLOWED_PURPOSES = frozenset({"m2_payment", "uat_signoff"})


@dataclass
class _OtpChallenge:
    challenge_id: str
    purpose: str
    project_id: str
    code: str
    expires_at: datetime


_challenges: dict[str, _OtpChallenge] = {}
_challenge_seq = itertools.count(1)


@dataclass
class _ProjectCommercial:
    contract_value_cents: int
    currency: str
    milestones: list[MilestonePaymentLine]
    budget_utilisation_pct: float
    m2_confirmed: bool = False
    m2_released: bool = False
    m3_invoiced: bool = False


_TAB8: dict[str, _ProjectCommercial] = {}


def _seed_commercial(project_id: str) -> _ProjectCommercial:
    if project_id in _TAB8:
        return _TAB8[project_id]

    row = _ProjectCommercial(
        contract_value_cents=180_000_00,
        currency="USD",
        milestones=[
            MilestonePaymentLine(
                milestone_key="M1",
                label="Design / discovery",
                amount_cents=45_000_00,
                status="released",
            ),
            MilestonePaymentLine(
                milestone_key="M2",
                label="Build & integration",
                amount_cents=72_000_00,
                status="pending",
            ),
            MilestonePaymentLine(
                milestone_key="M3",
                label="UAT & go-live",
                amount_cents=63_000_00,
                status="pending",
            ),
        ],
        budget_utilisation_pct=52.0,
    )
    _TAB8[project_id] = row
    return row


def get_commercial_summary(project_id: str) -> CommercialSummaryResponse | None:
    if not project_exists(project_id):
        return None

    commercial = _seed_commercial(project_id)
    milestone_payments: list[MilestonePaymentLine] = []
    for milestone in commercial.milestones:
        status = milestone.status
        if milestone.milestone_key == "M2":
            if commercial.m2_released:
                status = "released"
            elif commercial.m2_confirmed:
                status = "otp_verified"
        if milestone.milestone_key == "M3" and commercial.m3_invoiced:
            status = "invoiced"
        milestone_payments.append(
            MilestonePaymentLine(
                milestone_key=milestone.milestone_key,
                label=milestone.label,
                amount_cents=milestone.amount_cents,
                currency=milestone.currency,
                status=status,
            ),
        )

    return CommercialSummaryResponse(
        project_id=project_id,
        contract_value_cents=commercial.contract_value_cents,
        currency=commercial.currency,
        milestone_payments=milestone_payments,
        budget_utilisation_pct=commercial.budget_utilisation_pct,
    )


def _new_challenge(purpose: str, project_id: str) -> _OtpChallenge:
    code = "".join(random.choices(string.digits, k=6))
    challenge_id = f"ch_{next(_challenge_seq):05d}"
    expires_at = datetime.now(tz=_UTC) + _OTP_TTL
    challenge = _OtpChallenge(
        challenge_id=challenge_id,
        purpose=purpose,
        project_id=project_id,
        code=code,
        expires_at=expires_at,
    )
    _challenges[challenge_id] = challenge
    return challenge


def send_otp(purpose: str, project_id: str) -> tuple[SendOtpResponse | None, str | None]:
    normalized_purpose = purpose.strip().lower()
    if normalized_purpose not in _ALLOWED_PURPOSES:
        return None, "invalid_purpose"
    if not project_exists(project_id):
        return None, "project_not_found"

    challenge = _new_challenge(normalized_purpose, project_id)
    return (
        SendOtpResponse(
            challenge_id=challenge.challenge_id,
            expires_at=challenge.expires_at,
            message=(
                f"OTP issued for {normalized_purpose}. "
                "Use confirm endpoints with this code (demo)."
            ),
            demo_otp=challenge.code,
        ),
        None,
    )


def _resolve_challenge(
    purpose: str,
    project_id: str,
    otp: str,
    challenge_id: str | None,
) -> _OtpChallenge | None:
    now = datetime.now(tz=_UTC)
    if challenge_id:
        challenge = _challenges.get(challenge_id)
        if (
            challenge
            and challenge.purpose == purpose
            and challenge.project_id == project_id
            and challenge.code == otp.strip()
            and challenge.expires_at >= now
        ):
            return challenge
        return None

    for challenge in reversed(list(_challenges.values())):
        if (
            challenge.purpose == purpose
            and challenge.project_id == project_id
            and challenge.code == otp.strip()
            and challenge.expires_at >= now
        ):
            return challenge
    return None


def _consume_challenge(challenge: _OtpChallenge) -> None:
    _challenges.pop(challenge.challenge_id, None)


def confirm_m2_payment(
    project_id: str,
    *,
    otp: str,
    challenge_id: str | None,
) -> tuple[M2ConfirmResponse | None, str | None]:
    if not project_exists(project_id):
        return None, "project_not_found"

    commercial = _seed_commercial(project_id)
    if commercial.m2_released:
        return None, "already_released"

    challenge = _resolve_challenge("m2_payment", project_id, otp, challenge_id)
    if challenge is None:
        return None, "otp_invalid"

    _consume_challenge(challenge)
    commercial.m2_confirmed = True
    return (
        M2ConfirmResponse(
            project_id=project_id,
            message="M2 OTP verified. You may call the release endpoint.",
        ),
        None,
    )


def release_m2_payment(project_id: str) -> tuple[M2ReleaseResponse | None, str | None]:
    if not project_exists(project_id):
        return None, "project_not_found"

    commercial = _seed_commercial(project_id)
    if commercial.m2_released:
        return None, "already_released"
    if not commercial.m2_confirmed:
        return None, "otp_not_confirmed"

    milestone = next((row for row in commercial.milestones if row.milestone_key == "M2"), None)
    if milestone is None:
        return None, "no_m2"

    commercial.m2_released = True
    commercial.m2_confirmed = False
    released_at = datetime.now(tz=_UTC)
    return (
        M2ReleaseResponse(
            project_id=project_id,
            released_at=released_at,
            amount_cents=milestone.amount_cents,
            currency=milestone.currency,
        ),
        None,
    )


def start_uat_signoff(project_id: str) -> tuple[UatSignoffResponse | None, str | None]:
    if not project_exists(project_id):
        return None, "project_not_found"

    commercial = _seed_commercial(project_id)
    if commercial.m3_invoiced:
        return None, "already_invoiced"

    challenge = _new_challenge("uat_signoff", project_id)
    return (
        UatSignoffResponse(
            project_id=project_id,
            challenge_id=challenge.challenge_id,
            expires_at=challenge.expires_at,
            message="UAT sign-off OTP issued. Call /uat-signoff/confirm with the code.",
            demo_otp=challenge.code,
        ),
        None,
    )


def confirm_uat_signoff(
    project_id: str,
    *,
    otp: str,
    challenge_id: str | None,
) -> tuple[UatConfirmResponse | None, str | None]:
    if not project_exists(project_id):
        return None, "project_not_found"

    commercial = _seed_commercial(project_id)
    if commercial.m3_invoiced:
        return None, "already_invoiced"

    challenge = _resolve_challenge("uat_signoff", project_id, otp, challenge_id)
    if challenge is None:
        return None, "otp_invalid"

    _consume_challenge(challenge)
    commercial.m3_invoiced = True
    invoice_id = f"inv_m3_{project_id}_{next(_challenge_seq)}"
    return (
        UatConfirmResponse(
            project_id=project_id,
            invoice_id=invoice_id,
            message="M3 invoice generated after UAT OTP verification (demo).",
        ),
        None,
    )

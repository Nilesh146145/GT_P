from __future__ import annotations

import itertools
from datetime import datetime, timezone

UTC = timezone.utc  # Python 3.9 (datetime.UTC is 3.11+)

from app.project_portfolio.schemas.escalation import EscalationCreate, EscalationRecord
from app.project_portfolio.services.projects import project_exists
from app.project_portfolio.services.rework import get_rework_request, mark_rework_escalated

_ESCALATIONS: list[EscalationRecord] = []
_escalation_seq = itertools.count(1)


def raise_escalation(body: EscalationCreate) -> tuple[EscalationRecord | None, str | None]:
    if not project_exists(body.project_id):
        return None, "project_not_found"

    reason = (body.reason or "").strip()
    rework_id = body.rework_request_id
    rework_id_out: str | None = None

    if rework_id:
        rework = get_rework_request(body.project_id, rework_id)
        if rework is None:
            return None, "rework_not_found"
        if not reason:
            reason = rework.reason
        mark_rework_escalated(body.project_id, rework_id)
        rework_id_out = rework_id

    record = EscalationRecord(
        id=f"esc_{next(_escalation_seq):03d}",
        project_id=body.project_id,
        reason=reason,
        severity=body.severity,
        raised_at=datetime.now(tz=UTC),
        rework_request_id=rework_id_out,
    )
    _ESCALATIONS.append(record)
    return record, None


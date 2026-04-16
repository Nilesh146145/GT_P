from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # Python 3.9 (datetime.UTC is 3.11+)

from app.project_portfolio.schemas.escalation import EscalationCreate
from app.project_portfolio.schemas.exception import (
    ExceptionCreateRequest,
    ExceptionSeverity,
    ExceptionStatus,
    ProjectException,
)
from app.project_portfolio.services.escalations import raise_escalation
from app.project_portfolio.services.projects import project_exists

_seq = itertools.count(1)
_EXCEPTIONS: list[ProjectException] = []


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _auto_escalate(exc: ProjectException) -> ProjectException:
    if exc.status != ExceptionStatus.OPEN:
        return exc

    should_escalate = False
    now = _now()
    age = now - exc.created_at
    if exc.severity == ExceptionSeverity.CRITICAL:
        should_escalate = True
    elif exc.severity == ExceptionSeverity.HIGH and age > timedelta(hours=24):
        should_escalate = True
    elif exc.severity == ExceptionSeverity.MEDIUM and age > timedelta(hours=72):
        should_escalate = True
    else:
        week_ago = now - timedelta(days=7)
        repeated = sum(
            1
            for item in _EXCEPTIONS
            if item.project_id == exc.project_id and item.type == exc.type and item.created_at >= week_ago
        )
        if repeated >= 3:
            should_escalate = True

    if not should_escalate:
        return exc
    record, err = raise_escalation(
        EscalationCreate(
            project_id=exc.project_id,
            reason=f"Auto escalation from exception {exc.id}: {exc.title}",
            severity=exc.severity.value.lower(),
        ),
    )
    if err is None and record is not None:
        exc.status = ExceptionStatus.ESCALATED
        exc.escalation_id = record.id
    return exc


def create_exception(
    project_id: str,
    body: ExceptionCreateRequest,
) -> tuple[ProjectException | None, str | None]:
    if not project_exists(project_id):
        return None, "project_not_found"
    exc = ProjectException(
        id=f"exc_{next(_seq):04d}",
        project_id=project_id,
        type=body.type,
        severity=body.severity,
        status=ExceptionStatus.OPEN,
        title=body.title,
        detail=body.detail,
        created_at=_now(),
    )
    _EXCEPTIONS.append(exc)
    exc = _auto_escalate(exc)
    return exc, None


def list_exceptions(project_id: str) -> tuple[list[ProjectException] | None, str | None]:
    if not project_exists(project_id):
        return None, "project_not_found"
    rows = [exc for exc in _EXCEPTIONS if exc.project_id == project_id]
    for row in rows:
        _auto_escalate(row)
    rows.sort(key=lambda x: x.created_at, reverse=True)
    return rows, None

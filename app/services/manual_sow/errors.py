"""Spec §15 error JSON responses for Manual SOW routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi.responses import JSONResponse


class ManualSowSpecException(Exception):
    """Raised to return spec-shaped JSON errors (handled in main.py)."""

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(body.get("error", "error"))


def spec_error_json(
    *,
    status_code: int,
    error: str,
    error_code: str,
    details: Optional[dict[str, str]] = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    rid = request_id or str(uuid.uuid4())
    body: dict[str, Any] = {
        "error": error,
        "error_code": error_code,
        "status": status_code,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "request_id": rid,
    }
    return body


def raise_spec(status_code: int, error: str, error_code: str, details: Optional[dict[str, str]] = None) -> None:
    raise ManualSowSpecException(
        status_code,
        spec_error_json(
            status_code=status_code,
            error=error,
            error_code=error_code,
            details=details,
        ),
    )


def spec_error_response(
    *,
    status_code: int,
    error: str,
    error_code: str,
    details: Optional[dict[str, str]] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=spec_error_json(
            status_code=status_code,
            error=error,
            error_code=error_code,
            details=details,
            request_id=request_id,
        ),
    )

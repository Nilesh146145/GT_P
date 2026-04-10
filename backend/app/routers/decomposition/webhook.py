"""Internal AGI callback when a plan revision finishes (optional webhook secret)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Header, HTTPException, Path

from app.services.decomposition.plan_service import RevisionCompleteBody, complete_revision_after_agi

router = APIRouter(prefix="/internal/decomposition", tags=["Internal — Decomposition"])


@router.post("/plans/{plan_id}/revision/complete")
async def decomposition_revision_complete(
    plan_id: str = Path(..., description="Plan UUID"),
    x_gt_decomposition_webhook_secret: Annotated[str | None, Header()] = None,
    body: RevisionCompleteBody | None = Body(default=None),
):
    from app.core.config import settings

    if not settings.DECOMPOSITION_REVISION_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Decomposition revision webhook is not configured.")
    return await complete_revision_after_agi(plan_id, x_gt_decomposition_webhook_secret, body)

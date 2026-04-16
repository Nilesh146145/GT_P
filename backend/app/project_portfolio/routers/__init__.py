from __future__ import annotations

from fastapi import APIRouter

from app.project_portfolio.routers import (
    escalations,
    evidence,
    milestones,
    payments,
    portfolio,
    projects,
    tab8,
    team,
)

router = APIRouter()
router.include_router(portfolio.router)
router.include_router(projects.router)
router.include_router(payments.router)
router.include_router(milestones.router)
router.include_router(evidence.router)
router.include_router(team.router)
router.include_router(tab8.router)
router.include_router(escalations.router)

__all__ = ["router"]

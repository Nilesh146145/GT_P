from __future__ import annotations

from fastapi import APIRouter

from app.billing.routers import invoices, payments, refunds, summary

router = APIRouter(prefix="/billing", tags=["Billing"])
router.include_router(invoices.router)
router.include_router(payments.router)
router.include_router(refunds.router)
router.include_router(summary.router)

__all__ = ["router"]


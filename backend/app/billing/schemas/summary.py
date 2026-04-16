from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BillingSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_invoiced: float
    total_paid: float
    total_pending: float
    total_overdue: float
    currency: str

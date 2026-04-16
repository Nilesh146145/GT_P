from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class PayoutSortBy(str, Enum):
    REFERENCE = "reference"
    AMOUNT = "amount"
    METHOD = "method"
    STATUS = "status"
    DATE = "date"


class PayoutListItem(BaseModel):
    id: str
    reference: str
    amount: Decimal
    currency: str
    method: str
    status: str
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    bank_last4: Optional[str] = None


class PaginatedPayouts(BaseModel):
    items: List[PayoutListItem]
    page: int
    page_size: int
    total: int


class IncludedEarning(BaseModel):
    earning_id: str
    task_title: str
    amount: Decimal
    currency: str


class PayoutDetail(BaseModel):
    id: str
    reference: str
    amount: Decimal
    currency: str
    method: str
    status: str
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    bank_last4: Optional[str] = None
    earning_ids: List[str]
    included_earnings: List[IncludedEarning]

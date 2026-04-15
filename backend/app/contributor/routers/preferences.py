from __future__ import annotations

from fastapi import APIRouter, Depends

from app.contributor.schemas.preferences import PayoutPreferences, PayoutPreferencesUpdate
from app.contributor.dependencies import get_contributor_id
from app.contributor.services.earnings_data import contributor_data

router = APIRouter(
    prefix="/api/contributor",
    tags=["payout-preferences"],
    dependencies=[Depends(get_contributor_id)],
)


@router.get("/payout-preferences", response_model=PayoutPreferences)
def get_payout_preferences():
    return contributor_data.get_preferences()


@router.put("/payout-preferences", response_model=PayoutPreferences)
def put_payout_preferences(body: PayoutPreferencesUpdate):
    return contributor_data.update_preferences(body)

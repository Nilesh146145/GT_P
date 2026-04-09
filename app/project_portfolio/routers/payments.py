from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.project_portfolio.schemas.payment import (
    HoldPaymentResponse,
    PaymentHistoryResponse,
    PendingPaymentsResponse,
    ReleasePaymentResponse,
    SendOtpResponse,
)
from app.project_portfolio.services.payments import (
    hold_payment,
    list_payment_history,
    list_pending_payments,
    release_payment,
    send_payment_otp,
)

router = APIRouter(tags=["payments"])


class HoldPaymentBody(BaseModel):
    note: str | None = Field(default=None, description="Optional context for the escalation")


@router.get("/projects/{project_id}/payments/pending", response_model=PendingPaymentsResponse)
def get_pending_payments(project_id: str) -> PendingPaymentsResponse:
    out = list_pending_payments(project_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return out


@router.get("/projects/{project_id}/payments/history", response_model=PaymentHistoryResponse)
def get_payment_history(project_id: str) -> PaymentHistoryResponse:
    out = list_payment_history(project_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return out


@router.post(
    "/projects/{project_id}/payments/{payment_id}/send-otp",
    response_model=SendOtpResponse,
)
def post_send_payment_otp(project_id: str, payment_id: str) -> SendOtpResponse:
    resp, err = send_payment_otp(project_id, payment_id)
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    if err == "payment_not_found":
        raise HTTPException(status_code=404, detail="Payment not found")
    if err == "invalid_state":
        raise HTTPException(
            status_code=409,
            detail="Payment is not pending release (already held or released).",
        )
    assert resp is not None
    return resp


@router.get(
    "/projects/{project_id}/payments/{payment_id}/release",
    response_model=ReleasePaymentResponse,
)
def get_release_payment(
    project_id: str,
    payment_id: str,
    otp: str = Query(..., min_length=1, description="OTP from send-otp"),
) -> ReleasePaymentResponse:
    resp, err = release_payment(project_id, payment_id, otp=otp)
    if err == "otp_required":
        raise HTTPException(status_code=422, detail="OTP required")
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    if err == "payment_not_found":
        raise HTTPException(status_code=404, detail="Payment not found")
    if err == "invalid_state":
        raise HTTPException(status_code=409, detail="Payment cannot be released in current state.")
    if err == "otp_invalid":
        raise HTTPException(status_code=400, detail="Invalid OTP or OTP not requested")
    if err == "otp_expired":
        raise HTTPException(status_code=400, detail="OTP expired; request a new one")
    assert resp is not None
    return resp


@router.post(
    "/projects/{project_id}/payments/{payment_id}/hold",
    response_model=HoldPaymentResponse,
)
def post_hold_payment(
    project_id: str,
    payment_id: str,
    body: HoldPaymentBody | None = None,
) -> HoldPaymentResponse:
    note = body.note if body else None
    resp, err = hold_payment(project_id, payment_id, note=note)
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    if err == "payment_not_found":
        raise HTTPException(status_code=404, detail="Payment not found")
    if err == "invalid_state":
        raise HTTPException(status_code=409, detail="Payment is not pending release.")
    if err == "escalation_failed":
        raise HTTPException(status_code=500, detail="Escalation could not be created")
    assert resp is not None
    return resp

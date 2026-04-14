from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.project_portfolio.schemas.tab8 import (
    CommercialSummaryResponse,
    M2ConfirmResponse,
    M2ReleaseResponse,
    OtpConfirmBody,
    SendOtpRequest,
    SendOtpResponse,
    UatConfirmResponse,
    UatSignoffResponse,
)
from app.project_portfolio.services.tab8 import (
    confirm_m2_payment,
    confirm_uat_signoff,
    get_commercial_summary,
    release_m2_payment,
    send_otp,
    start_uat_signoff,
)

router = APIRouter(tags=["commercial"])


@router.get("/projects/{project_id}/commercial", response_model=CommercialSummaryResponse)
def get_commercial(project_id: str) -> CommercialSummaryResponse:
    out = get_commercial_summary(project_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return out


@router.post("/auth/send-otp", response_model=SendOtpResponse)
def post_send_otp(body: SendOtpRequest) -> SendOtpResponse:
    resp, err = send_otp(body.purpose.strip(), body.project_id)
    if err == "invalid_purpose":
        raise HTTPException(status_code=422, detail="purpose must be m2_payment or uat_signoff")
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    assert resp is not None
    return resp


@router.post("/payments/milestone/m2/{project_id}/confirm", response_model=M2ConfirmResponse)
def post_m2_confirm(project_id: str, body: OtpConfirmBody) -> M2ConfirmResponse:
    resp, err = confirm_m2_payment(
        project_id,
        otp=body.otp,
        challenge_id=body.challenge_id,
    )
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    if err == "already_released":
        raise HTTPException(status_code=409, detail="M2 already released")
    if err == "otp_invalid":
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    assert resp is not None
    return resp


@router.post("/payments/milestone/m2/{project_id}/release", response_model=M2ReleaseResponse)
def post_m2_release(project_id: str) -> M2ReleaseResponse:
    resp, err = release_m2_payment(project_id)
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    if err == "already_released":
        raise HTTPException(status_code=409, detail="M2 already released")
    if err == "otp_not_confirmed":
        raise HTTPException(
            status_code=403,
            detail="Call /payments/milestone/m2/{project_id}/confirm with OTP first",
        )
    if err == "no_m2":
        raise HTTPException(status_code=500, detail="M2 milestone missing")
    assert resp is not None
    return resp


@router.post("/projects/{project_id}/uat-signoff", response_model=UatSignoffResponse)
def post_uat_signoff(project_id: str) -> UatSignoffResponse:
    resp, err = start_uat_signoff(project_id)
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    if err == "already_invoiced":
        raise HTTPException(status_code=409, detail="M3 already invoiced")
    assert resp is not None
    return resp


@router.post("/projects/{project_id}/uat-signoff/confirm", response_model=UatConfirmResponse)
def post_uat_signoff_confirm(project_id: str, body: OtpConfirmBody) -> UatConfirmResponse:
    resp, err = confirm_uat_signoff(
        project_id,
        otp=body.otp,
        challenge_id=body.challenge_id,
    )
    if err == "project_not_found":
        raise HTTPException(status_code=404, detail="Project not found")
    if err == "already_invoiced":
        raise HTTPException(status_code=409, detail="M3 already invoiced")
    if err == "otp_invalid":
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    assert resp is not None
    return resp

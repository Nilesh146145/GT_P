"""
Verification schemas — derived from app/schemas/verification.py.
"""

from pydantic import BaseModel


class OtpSendRequest(BaseModel):
    registration_id: str
    destination: str


class OtpSendResponse(BaseModel):
    sent: bool
    expires_in_seconds: int
    resend_in_seconds: int


class OtpVerifyRequest(BaseModel):
    registration_id: str
    destination: str
    otp: str


class OtpVerifyResponse(BaseModel):
    verified: bool
    channel: str

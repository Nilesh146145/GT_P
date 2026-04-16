"""
MFA schemas — derived from app/schemas/mfa.py in the reference app.
"""

from typing import List, Optional

from pydantic import BaseModel


class MfaVerifyRequest(BaseModel):
    challenge_id: Optional[str] = None
    method: Optional[str] = None
    code: str


class TotpStartResponse(BaseModel):
    secret: str
    otpauth_uri: str


class RecoveryCodesResponse(BaseModel):
    recovery_codes: List[str]


class MfaMethodItem(BaseModel):
    id: str
    type: str
    is_primary: bool
    enabled: bool


class MfaMethodsResponse(BaseModel):
    methods: List[MfaMethodItem]

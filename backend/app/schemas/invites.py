"""
Invite schemas — derived from app/schemas/invites.py.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class CreateInviteRequest(BaseModel):
    tenant_id: str
    email: EmailStr
    role: str
    project: Optional[str] = None


class CreateInviteResponse(BaseModel):
    invite_id: str
    expires_at: datetime


class InviteMetadataResponse(BaseModel):
    valid: bool
    email_masked: str
    role: str
    tenant_name: Optional[str] = None
    expires_at: datetime


class AcceptInviteRequest(BaseModel):
    password: str
    confirm_password: str


class AcceptInviteResponse(BaseModel):
    user_id: str
    next_step: str

"""
SSO schemas — derived from app/schemas/sso.py in the reference app.
"""

from typing import List, Optional

from pydantic import BaseModel, EmailStr


class SsoDiscoverRequest(BaseModel):
    email: EmailStr


class SsoProviderSummary(BaseModel):
    id: str
    type: str
    name: str


class SsoDiscoverResponse(BaseModel):
    tenant_id: Optional[str] = None
    providers: List[SsoProviderSummary]


class SsoProviderCreateRequest(BaseModel):
    tenant_id: str
    type: str
    name: str
    issuer: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    metadata_url: Optional[str] = None
    entrypoint: Optional[str] = None
    certificate: Optional[str] = None


class SsoProviderResponse(BaseModel):
    id: str
    tenant_id: str
    type: str
    name: str
    issuer: str
    enabled: bool


class SsoProviderListResponse(BaseModel):
    providers: List[SsoProviderResponse]

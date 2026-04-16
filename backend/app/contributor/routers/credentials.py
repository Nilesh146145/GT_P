from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse

from app.contributor.schemas.credentials import (
    AcademicPortfolioRequest,
    AcademicPortfolioResponse,
    CredentialDetail,
    CredentialListResponse,
    CredentialShareRequest,
    CredentialWalletCardsResponse,
    DateFilter,
    PublicCredentialView,
    ShareResponse,
    SkillVerificationResponse,
    WalletSummaryResponse,
)
from app.contributor.dependencies import get_contributor_id
from app.contributor.services.credentials_store import store

router = APIRouter(
    prefix="/api/contributor/credentials",
    tags=["contributor-credentials"],
    dependencies=[Depends(get_contributor_id)],
)
public_router = APIRouter(prefix="/api/public/credentials", tags=["public-credentials"])


@router.get("/wallet/summary", response_model=WalletSummaryResponse)
def get_wallet_summary() -> WalletSummaryResponse:
    return store.wallet_summary()


@router.get("/wallet/cards", response_model=CredentialWalletCardsResponse)
def list_wallet_cards(
    skill: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CredentialWalletCardsResponse:
    return store.wallet_cards(skill, page, page_size)


@router.get("/skills/verification", response_model=SkillVerificationResponse)
def get_skill_verification_status() -> SkillVerificationResponse:
    return store.skill_verification()


@router.get("", response_model=CredentialListResponse)
def list_credentials(
    skill: str | None = Query(default=None),
    date_filter: DateFilter | None = Query(default=None, alias="date_filter"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CredentialListResponse:
    return store.list_credentials(skill, date_filter, page, page_size)


@router.get("/{credential_id}", response_model=CredentialDetail)
def get_credential(credential_id: str) -> CredentialDetail:
    return store.credential_detail(credential_id)


@router.get("/{credential_id}/certificate")
def get_certificate(
    credential_id: str,
    format: str = Query(default="pdf", description="Export format"),
) -> Response:
    fmt = format.lower().strip()
    if fmt != "pdf":
        raise HTTPException(status_code=400, detail="Unsupported format; use format=pdf")
    url = store.certificate_redirect_url(credential_id)
    return RedirectResponse(url=url, status_code=302)


@router.get("/{credential_id}/verification")
def get_verification(credential_id: str) -> dict[str, Any]:
    return store.verification_json(credential_id)


@router.post("/{credential_id}/share", response_model=ShareResponse)
def share_credential(credential_id: str, body: CredentialShareRequest) -> ShareResponse:
    return store.share(credential_id, body)


@public_router.get(
    "/{share_id}",
    response_model=PublicCredentialView,
    summary="Public credential by share link",
    description=(
        "Unauthenticated view for a shared credential. Returns only safe portfolio fields "
        "(task type, skills, designation, seniority, quality indicator, platform verified); "
        "excludes client-sensitive data such as emails, PODL hashes, and certificate URLs."
    ),
)
def get_public_credential(share_id: str) -> PublicCredentialView:
    return store.public_view(share_id)


@router.post("/{credential_id}/academic-portfolio", response_model=AcademicPortfolioResponse)
def create_academic_portfolio(
    credential_id: str,
    body: AcademicPortfolioRequest,
) -> AcademicPortfolioResponse:
    store.get_row_or_404(credential_id)
    fmt = (body.format or "pdf").lower().strip()
    if fmt != "pdf":
        raise HTTPException(status_code=400, detail="Only pdf is supported in this stub")
    job_id = str(uuid4())
    return AcademicPortfolioResponse(
        credential_id=credential_id,
        format=fmt,
        download_url=f"https://cdn.example.com/portfolio/{credential_id}/{job_id}.pdf",
        job_id=job_id,
    )

"""Credential demo persistence and business logic (in-memory). Routers stay thin."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.contributor.schemas.credentials import (
    CredentialDetail,
    CredentialListItem,
    CredentialListResponse,
    CredentialWalletCard,
    CredentialWalletCardsResponse,
    CredentialShareRequest,
    DateFilter,
    PublicCredentialView,
    ShareResponse,
    SkillVerificationItem,
    SkillVerificationResponse,
    WalletSummaryResponse,
)


def _quality_indicator(review_score: float | None) -> str | None:
    if review_score is None or review_score < 3:
        return None
    if review_score >= 5:
        return "Exceptional"
    if review_score >= 4:
        return "Strong"
    return "Standard"


class CredentialStore:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self._credentials: dict[str, dict[str, Any]] = {
            "cred-001": {
                "title": "Advanced Python Contribution",
                "skill": "python",
                "level": "L3",
                "issued_at": now - timedelta(days=10),
                "task_id": "task-42",
                "task_title": "Implement credential API",
                "project_title": "Glimmora Contributor",
                "podl_hash": "sha256:deadbeef...",
                "verification_url": "https://example.com/verify/cred-001",
                "review_score": 4.8,
                "hours_validated": 12.5,
                "certificate_file_url": "https://cdn.example.com/certs/cred-001.pdf",
                "academic_mapping": {"label": "CS elective", "credits": 3.0, "course_code": "CS-499"},
                "revoked": False,
                "task_type": "Frontend Component Development",
                "skill_tags": ["python", "fastapi", "api-design"],
                "designation": "Software Contributor",
                "seniority": "L3",
                "acceptance_date": now - timedelta(days=10),
                "acceptance_rate": 92.0,
                "platform_verified": True,
            },
        }
        self._share_links: dict[str, dict[str, str]] = {}
        self._skill_verification: list[dict[str, Any]] = [
            {
                "skill_tag": "python",
                "status": "VERIFIED",
                "credential_count": 3,
                "evidence_source": "assessment+accepted_tasks",
                "seniority_level": "L3",
            },
            {
                "skill_tag": "react",
                "status": "VERIFIED",
                "credential_count": 2,
                "evidence_source": "accepted_tasks",
                "seniority_level": "L3",
            },
            {
                "skill_tag": "system-design",
                "status": "DECLARED",
                "credential_count": 0,
                "evidence_source": "self_declared",
                "seniority_level": "L2",
            },
        ]

    def get_row_or_404(self, credential_id: str) -> dict[str, Any]:
        if credential_id not in self._credentials:
            raise HTTPException(status_code=404, detail="Credential not found")
        return self._credentials[credential_id]

    def _list_items(self) -> list[CredentialListItem]:
        out: list[CredentialListItem] = []
        for cid, row in self._credentials.items():
            out.append(
                CredentialListItem(
                    id=cid,
                    title=row["title"],
                    skill=row["skill"],
                    level=row["level"],
                    issued_at=row["issued_at"],
                    task_id=row["task_id"],
                    task_title=row["task_title"],
                    project_title=row["project_title"],
                    podl_hash=row["podl_hash"],
                    verification_url=row["verification_url"],
                    review_score=row.get("review_score"),
                    hours_validated=row.get("hours_validated"),
                    academic_mapping=row.get("academic_mapping"),
                    skill_tags=row.get("skill_tags"),
                    designation=row.get("designation"),
                    seniority=row.get("seniority"),
                    acceptance_date=row.get("acceptance_date"),
                    quality_indicator=_quality_indicator(row.get("review_score")),
                    platform_verified=row.get("platform_verified", True),
                )
            )
        return out

    @staticmethod
    def _filter_by_skill(items: list[CredentialListItem], skill: str | None) -> list[CredentialListItem]:
        if not skill:
            return items
        s = skill.strip().lower()
        return [i for i in items if i.skill.lower() == s]

    @staticmethod
    def _filter_by_date(items: list[CredentialListItem], date_filter: DateFilter | None) -> list[CredentialListItem]:
        if date_filter is None:
            return items
        now = datetime.now(timezone.utc)
        if date_filter == DateFilter.D30:
            cutoff = now - timedelta(days=30)
        elif date_filter == DateFilter.D90:
            cutoff = now - timedelta(days=90)
        else:
            cutoff = now - timedelta(days=183)
        return [i for i in items if i.issued_at >= cutoff]

    def _to_wallet_card(
        self, credential_id: str, row: dict[str, Any], shareable_link: str | None = None
    ) -> CredentialWalletCard:
        task_type = row.get("task_type", row.get("title", "Task Delivery"))
        return CredentialWalletCard(
            credential_id=credential_id,
            credential_title=f"Delivered: {task_type}",
            task_type=task_type,
            skill_tags=row.get("skill_tags", [row.get("skill", "")]),
            designation=row.get("designation", "Contributor"),
            seniority=row.get("seniority", row.get("level", "L1")),
            acceptance_date=row.get("acceptance_date", row["issued_at"]),
            quality_indicator=_quality_indicator(row.get("review_score")),
            platform_verified=row.get("platform_verified", True),
            certificate_pdf_url=row.get("certificate_file_url"),
            shareable_link=shareable_link,
        )

    def wallet_summary(self) -> WalletSummaryResponse:
        credentials = list(self._credentials.values())
        total_credentials = len(credentials)
        tasks_accepted = total_credentials
        verified_skills = {
            item["skill_tag"] for item in self._skill_verification if item["status"] == "VERIFIED"
        }
        avg_acceptance_rate = (
            sum(float(item.get("acceptance_rate", 0.0)) for item in credentials) / total_credentials
            if total_credentials
            else 0.0
        )
        return WalletSummaryResponse(
            total_credentials=total_credentials,
            skills_verified=len(verified_skills),
            tasks_accepted=tasks_accepted,
            acceptance_rate=round(avg_acceptance_rate, 2),
        )

    def wallet_cards(
        self, skill: str | None, page: int, page_size: int
    ) -> CredentialWalletCardsResponse:
        cards: list[CredentialWalletCard] = []
        for credential_id, row in self._credentials.items():
            cards.append(self._to_wallet_card(credential_id, row))
        cards.sort(key=lambda c: c.acceptance_date, reverse=True)
        if skill:
            normalized = skill.strip().lower()
            cards = [c for c in cards if any(tag.lower() == normalized for tag in c.skill_tags)]
        total = len(cards)
        start = (page - 1) * page_size
        end = start + page_size
        return CredentialWalletCardsResponse(items=cards[start:end], page=page, page_size=page_size, total=total)

    def skill_verification(self) -> SkillVerificationResponse:
        return SkillVerificationResponse(
            items=[SkillVerificationItem(**item) for item in self._skill_verification]
        )

    def list_credentials(
        self,
        skill: str | None,
        date_filter: DateFilter | None,
        page: int,
        page_size: int,
    ) -> CredentialListResponse:
        items = self._filter_by_skill(self._list_items(), skill)
        items = self._filter_by_date(items, date_filter)
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]
        return CredentialListResponse(
            items=page_items,
            page=page,
            page_size=page_size,
            total=total,
        )

    def credential_detail(self, credential_id: str) -> CredentialDetail:
        row = self.get_row_or_404(credential_id)
        return CredentialDetail(
            title=row["title"],
            skill=row["skill"],
            level=row["level"],
            issued_at=row["issued_at"],
            task_id=row["task_id"],
            task_title=row["task_title"],
            project_title=row["project_title"],
            podl_hash=row["podl_hash"],
            verification_url=row["verification_url"],
            review_score=row.get("review_score"),
            hours_validated=row.get("hours_validated"),
            certificate_file_url=row.get("certificate_file_url"),
            academic_mapping=row.get("academic_mapping"),
            revoked=row.get("revoked", False),
            skill_tags=row.get("skill_tags"),
            designation=row.get("designation"),
            seniority=row.get("seniority"),
            acceptance_date=row.get("acceptance_date"),
            quality_indicator=_quality_indicator(row.get("review_score")),
            platform_verified=row.get("platform_verified", True),
        )

    def certificate_redirect_url(self, credential_id: str) -> str:
        self.get_row_or_404(credential_id)
        url = self._credentials[credential_id].get("certificate_file_url")
        if not url:
            raise HTTPException(status_code=404, detail="Certificate file not available")
        return url

    def verification_json(self, credential_id: str) -> dict[str, Any]:
        row = self.get_row_or_404(credential_id)
        return {
            "credential_id": credential_id,
            "podl_hash": row["podl_hash"],
            "verification_url": row["verification_url"],
            "revoked": row.get("revoked", False),
            "issued_at": row["issued_at"].isoformat(),
            "platform_verified": row.get("platform_verified", True),
        }

    def share(self, credential_id: str, body: CredentialShareRequest) -> ShareResponse:
        self.get_row_or_404(credential_id)
        if not body.target_type or not body.target_type.strip():
            raise HTTPException(status_code=422, detail="target_type is required")
        if body.consent is not True:
            raise HTTPException(status_code=422, detail="consent must be true to share credential")
        share_id = str(uuid4())
        public_url = f"https://glimmora.example/public/credentials/{share_id}"
        self._share_links[share_id] = {
            "credential_id": credential_id,
            "target_type": body.target_type.strip(),
            "target_id": body.target_id or "",
        }
        return ShareResponse(
            credential_id=credential_id,
            share_id=share_id,
            status="created",
            target_type=body.target_type.strip(),
            target_id=body.target_id,
            public_url=public_url,
        )

    def public_view(self, share_id: str) -> PublicCredentialView:
        shared = self._share_links.get(share_id)
        if not shared:
            raise HTTPException(status_code=404, detail="Shared credential not found")
        row = self.get_row_or_404(shared["credential_id"])
        return PublicCredentialView(
            task_type=row.get("task_type", row.get("title", "Task Delivery")),
            skills_evidenced=row.get("skill_tags", [row.get("skill", "")]),
            designation=row.get("designation", "Contributor"),
            seniority=row.get("seniority", row.get("level", "L1")),
            quality_indicator=_quality_indicator(row.get("review_score")),
            platform_verified=row.get("platform_verified", True),
        )

    def apply_temp_demo_seed(self) -> None:
        now = datetime.now(timezone.utc)
        self._share_links.setdefault(
            "share_demo_public",
            {"credential_id": "cred-001", "target_type": "university", "target_id": ""},
        )
        if "cred-002" not in self._credentials:
            self._credentials["cred-002"] = {
                "title": "Data labeling quality lead",
                "skill": "annotation",
                "level": "L2",
                "issued_at": now - timedelta(days=45),
                "task_id": "task-88",
                "task_title": "Taxonomy QA sprint",
                "project_title": "Retail CV",
                "podl_hash": "sha256:cafebabe...",
                "verification_url": "https://example.com/verify/cred-002",
                "review_score": 4.2,
                "hours_validated": 40.0,
                "certificate_file_url": "https://cdn.example.com/certs/cred-002.pdf",
                "academic_mapping": None,
                "revoked": False,
                "task_type": "Multimodal labeling",
                "skill_tags": ["annotation", "qa", "cv"],
                "designation": "Senior labeler",
                "seniority": "L2",
                "acceptance_date": now - timedelta(days=45),
                "acceptance_rate": 88.0,
                "platform_verified": True,
            }
            self._skill_verification.append(
                {
                    "skill_tag": "typescript",
                    "status": "DECLARED",
                    "credential_count": 0,
                    "evidence_source": "self_declared",
                    "seniority_level": "L2",
                }
            )
        if "cred-003" not in self._credentials:
            self._credentials["cred-003"] = {
                "title": "Legacy course certificate (revoked)",
                "skill": "general",
                "level": "L1",
                "issued_at": now - timedelta(days=400),
                "task_id": "task-legacy",
                "task_title": "Intro program",
                "project_title": "Archive",
                "podl_hash": "sha256:00000000",
                "verification_url": "https://example.com/verify/cred-003",
                "review_score": 3.0,
                "hours_validated": 2.0,
                "certificate_file_url": None,
                "academic_mapping": None,
                "revoked": True,
                "task_type": "Orientation",
                "skill_tags": ["general"],
                "designation": "Contributor",
                "seniority": "L1",
                "acceptance_date": now - timedelta(days=400),
                "acceptance_rate": 70.0,
                "platform_verified": False,
            }


store = CredentialStore()


def apply_temp_demo_seed() -> None:
    store.apply_temp_demo_seed()

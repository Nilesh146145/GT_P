from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone

UTC = timezone.utc  # Python 3.9 (datetime.UTC is 3.11+)

from app.project_portfolio.schemas.evidence import (
    EvidencePackGroup,
    EvidencePackItem,
    EvidencePackStatus,
    EvidencePacksResponse,
)
from app.project_portfolio.schemas.evidence_detail import EvidenceArtifact, EvidencePackDetail
from app.project_portfolio.services.projects import project_exists


def _d(y: int, m: int, d_: int) -> datetime:
    return datetime(y, m, d_, 12, 0, tzinfo=UTC)


_EVIDENCE_BY_PROJECT: dict[str, list[EvidencePackItem]] = {
    "proj_001": [
        EvidencePackItem(
            id="ep_p1_01",
            title="Brand guidelines PDF",
            status=EvidencePackStatus.APPROVED,
            milestone_id="ms_proj_001_m1",
            milestone_key="M1",
            submitted_at=_d(2026, 3, 5),
        ),
        EvidencePackItem(
            id="ep_p1_02",
            title="Design review notes",
            status=EvidencePackStatus.PENDING_REVIEW,
            milestone_id="ms_proj_001_m1",
            milestone_key="M1",
            submitted_at=_d(2026, 3, 12),
        ),
        EvidencePackItem(
            id="ep_p1_03",
            title="Accessibility checklist",
            status=EvidencePackStatus.PENDING_REVIEW,
            milestone_id="ms_proj_001_m2",
            milestone_key="M2",
            submitted_at=_d(2026, 3, 25),
        ),
        EvidencePackItem(
            id="ep_p1_04",
            title="QA sign-off bundle",
            status=EvidencePackStatus.DRAFT,
            milestone_id="ms_proj_001_m2",
            milestone_key="M2",
            submitted_at=_d(2026, 4, 2),
        ),
        EvidencePackItem(
            id="ep_p1_05",
            title="Stakeholder approval email",
            status=EvidencePackStatus.REJECTED,
            milestone_id="ms_proj_001_m2",
            milestone_key="M2",
            submitted_at=_d(2026, 3, 28),
        ),
        EvidencePackItem(
            id="ep_p1_06",
            title="Launch comms pack",
            status=EvidencePackStatus.PENDING_REVIEW,
            milestone_id="ms_proj_001_m2",
            milestone_key="M2",
            submitted_at=_d(2026, 4, 5),
        ),
    ],
    "proj_002": [
        EvidencePackItem(
            id="ep_p2_01",
            title="Schema diagram",
            status=EvidencePackStatus.PENDING_REVIEW,
            milestone_id="ms_proj_002_m1",
            milestone_key="M1",
            submitted_at=_d(2026, 3, 18),
        ),
    ],
    "proj_003": [
        EvidencePackItem(
            id="ep_p3_01",
            title="Beta crash export",
            status=EvidencePackStatus.PENDING_REVIEW,
            milestone_id="ms_proj_003_m1",
            milestone_key="M1",
            submitted_at=_d(2026, 4, 3),
        ),
    ],
    "proj_004": [
        EvidencePackItem(
            id="ep_p4_01",
            title="Retro summary",
            status=EvidencePackStatus.APPROVED,
            milestone_id="ms_proj_004_m1",
            milestone_key="M1",
            submitted_at=_d(2026, 4, 7),
        ),
    ],
}

_MILESTONE_NAMES: dict[str, str] = {
    "ms_proj_001_m1": "Design freeze",
    "ms_proj_001_m2": "Build & QA",
    "ms_proj_002_m1": "Pipeline MVP",
    "ms_proj_003_m1": "Beta readiness",
    "ms_proj_004_m1": "Retrospective",
}

_EVIDENCE_INDEX: dict[str, tuple[str, EvidencePackItem]] = {}
for _pid, _packs in _EVIDENCE_BY_PROJECT.items():
    for _pack in _packs:
        _EVIDENCE_INDEX[_pack.id] = (_pid, _pack)

_EVIDENCE_DETAIL_EXTRA: dict[str, dict] = {
    "ep_p1_01": {
        "summary": "Signed-off brand palette, typography, and logo usage.",
        "reviewer_notes": "Approved with minor copy edits in section 2.",
        "artifacts": [
            {"name": "brand-guidelines.pdf", "content_type": "application/pdf", "url": None},
            {"name": "logo-pack.zip", "content_type": "application/zip", "url": None},
        ],
    },
    "ep_p1_02": {
        "summary": "Notes from cross-functional design review.",
        "reviewer_notes": None,
        "artifacts": [
            {"name": "design-review-notes.md", "content_type": "text/markdown", "url": None},
        ],
    },
    "ep_p1_03": {
        "summary": "WCAG-oriented checklist for core flows.",
        "reviewer_notes": "Pending design updates for contrast tokens.",
        "artifacts": [],
    },
}


def get_evidence_pack_detail(evidence_id: str) -> EvidencePackDetail | None:
    entry = _EVIDENCE_INDEX.get(evidence_id)
    if entry is None:
        return None
    project_id, pack = entry
    meta = _EVIDENCE_DETAIL_EXTRA.get(
        evidence_id,
        {
            "summary": f'Evidence pack "{pack.title}" for milestone {pack.milestone_key}.',
            "reviewer_notes": None,
            "artifacts": [],
        },
    )
    arts = [
        EvidenceArtifact(**a) if isinstance(a, dict) else a
        for a in meta.get("artifacts", [])
    ]
    return EvidencePackDetail(
        id=pack.id,
        project_id=project_id,
        title=pack.title,
        status=pack.status,
        milestone_id=pack.milestone_id,
        milestone_key=pack.milestone_key,
        milestone_name=_MILESTONE_NAMES.get(pack.milestone_id),
        submitted_at=pack.submitted_at,
        summary=meta.get("summary"),
        reviewer_notes=meta.get("reviewer_notes"),
        artifacts=arts,
    )


def _matches_milestone(pack: EvidencePackItem, milestone_id: str | None) -> bool:
    if not milestone_id:
        return True
    raw = milestone_id.strip()
    if not raw:
        return True
    if raw == pack.milestone_id:
        return True
    return pack.milestone_key.upper() == raw.upper()


def _matches_dates(
    pack: EvidencePackItem,
    start_date: date | None,
    end_date: date | None,
) -> bool:
    submitted_date = pack.submitted_at.date()
    if start_date is not None and submitted_date < start_date:
        return False
    if end_date is not None and submitted_date > end_date:
        return False
    return True


def list_evidence_packs(
    project_id: str,
    *,
    status: EvidencePackStatus | None,
    milestone_id: str | None,
    start_date: date | None,
    end_date: date | None,
    page: int,
    limit: int,
) -> EvidencePacksResponse | None:
    if not project_exists(project_id):
        return None
    packs = list(_EVIDENCE_BY_PROJECT.get(project_id, []))
    filtered: list[EvidencePackItem] = []
    for pack in packs:
        if status is not None and pack.status != status:
            continue
        if not _matches_milestone(pack, milestone_id):
            continue
        if not _matches_dates(pack, start_date, end_date):
            continue
        filtered.append(pack)

    filtered.sort(key=lambda x: x.submitted_at, reverse=True)
    total = len(filtered)
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit
    page_rows = filtered[offset : offset + limit]

    by_ms: dict[str, list[EvidencePackItem]] = defaultdict(list)
    order: list[str] = []
    for pack in page_rows:
        if pack.milestone_id not in order:
            order.append(pack.milestone_id)
        by_ms[pack.milestone_id].append(pack)

    groups: list[EvidencePackGroup] = []
    for milestone_id_value in order:
        items = by_ms[milestone_id_value]
        if not items:
            continue
        milestone_key = items[0].milestone_key
        groups.append(
            EvidencePackGroup(
                milestone_id=milestone_id_value,
                milestone_key=milestone_key,
                milestone_name=_MILESTONE_NAMES.get(milestone_id_value),
                evidence_packs=items,
            ),
        )

    return EvidencePacksResponse(
        project_id=project_id,
        page=page,
        limit=limit,
        total=total,
        start_date=start_date,
        end_date=end_date,
        status_filter=status,
        milestone_filter=milestone_id.strip() if milestone_id else None,
        groups=groups,
    )


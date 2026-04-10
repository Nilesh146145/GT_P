"""Derive gap items from accepted extraction coverage (spec §7)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Set

from app.schemas.manual_sow.enums import ExtractionCategory, GapSeverity


def _accepted_text_by_category(items: List[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for it in items:
        if it.get("review_state") not in ("accepted", "edited"):
            continue
        cat = it.get("category") or ""
        text = it.get("edited_text") if it.get("review_state") == "edited" else it.get("text")
        out[cat] = (out.get(cat, "") + " " + (text or "")).strip()
    return out


def build_gap_items(extraction_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Static checklist vs categories present in accepted/edited items."""
    by_cat = _accepted_text_by_category(extraction_items)
    present: Set[str] = set(by_cat.keys())

    templates: List[Dict[str, Any]] = [
        {
            "severity": GapSeverity.critical.value,
            "title": "Missing Acceptance Criteria",
            "description": "No formal acceptance criteria detected in accepted extractions.",
            "section": "Quality",
            "needs": {ExtractionCategory.features.value},
        },
        {
            "severity": GapSeverity.important.value,
            "title": "Budget clarity",
            "description": "Budget range or commercial terms may be incomplete.",
            "section": "Budget",
            "needs": {ExtractionCategory.budget.value},
        },
        {
            "severity": GapSeverity.important.value,
            "title": "Timeline milestones",
            "description": "Timeline or milestone language not clearly extracted.",
            "section": "Timeline",
            "needs": {ExtractionCategory.timeline.value},
        },
        {
            "severity": GapSeverity.optional.value,
            "title": "Risk register",
            "description": "Consider documenting known risks explicitly.",
            "section": "Risk",
            "needs": {ExtractionCategory.risk.value},
        },
    ]

    gaps: List[Dict[str, Any]] = []
    for t in templates:
        if present & t["needs"]:
            continue
        gaps.append(
            {
                "public_id": str(uuid.uuid4()),
                "severity": t["severity"],
                "title": t["title"],
                "description": t["description"],
                "section": t["section"],
                "is_resolved": False,
                "is_acknowledged": False,
                "is_dismissed": False,
                "is_prohibited": False,
                "prohibited_reason": None,
                "remediation_suggestions": [
                    "Accept or edit an extraction item covering this topic.",
                    "Or acknowledge this gap if acceptable for your organisation.",
                ],
            }
        )

    return gaps

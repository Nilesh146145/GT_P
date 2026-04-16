"""Progression gates (spec §16.2)."""

from __future__ import annotations

from typing import Any, Dict, List

from app.schemas.manual_sow.enums import CommercialSectionKey, ExtractionCategory, GapSeverity


def gate_step3_to_4(extraction_items: List[Dict[str, Any]]) -> bool:
    for it in extraction_items:
        if it.get("category") != ExtractionCategory.features.value:
            continue
        st = it.get("review_state")
        if st in ("accepted", "edited"):
            return True
    return False


def gate_step4_to_5(gap_items: List[Dict[str, Any]]) -> bool:
    for g in gap_items:
        sev = g.get("severity")
        if sev == GapSeverity.critical.value and not g.get("is_resolved"):
            return False
        if sev == GapSeverity.important.value:
            if not (g.get("is_resolved") or g.get("is_acknowledged")):
                return False
    return True


def gate_step5_to_6(section_status: Dict[str, str], authorities: Dict[str, Any]) -> bool:
    from app.services.manual_sow.commercial_validation import all_sections_complete, validate_approvers

    if not all_sections_complete(section_status):
        return False
    ok, _ = validate_approvers(authorities or {})
    return ok

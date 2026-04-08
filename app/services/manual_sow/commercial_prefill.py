"""
Derive commercial-details sections from parsed extraction items + report (manual SOW intake).

Seeds businessContext and techIntegrations so GET /sow/{id}/commercial-details returns
AI-grounded defaults; users may override via PATCH.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.schemas.manual_sow.enums import ExtractionCategory

# Minimum lengths enforced by commercial_validation.validate_section
_MIN_PROJECT_VISION = 50
_MIN_TECH_STACK = 10

_TECH_KEYWORDS = (
    "python",
    "fastapi",
    "django",
    "flask",
    "react",
    "angular",
    "vue",
    "next.js",
    "nextjs",
    "node",
    "nodejs",
    "typescript",
    "javascript",
    "java",
    "spring",
    "dotnet",
    ".net",
    "c#",
    "go",
    "rust",
    "ruby",
    "rails",
    "php",
    "laravel",
    "kubernetes",
    "docker",
    "aws",
    "azure",
    "gcp",
    "postgres",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "graphql",
    "rest api",
    "kafka",
    "terraform",
    "snowflake",
    "salesforce",
    "sap",
)


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False


def _join_item_texts(items: List[Dict[str, Any]], categories: Optional[set[str]] = None) -> str:
    parts: List[str] = []
    for it in items:
        cat = it.get("category") or ""
        if categories is not None and cat not in categories:
            continue
        t = (it.get("text") or "").strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts)


def _pad_vision(text: str, title: str, client: str) -> str:
    base = (text or "").strip()
    if len(base) >= _MIN_PROJECT_VISION:
        return base
    filler = (
        f" Project context for {client}: deliver the outcomes described in the uploaded SOW and reviewed "
        f"extraction items for “{title}”. Stakeholders should validate scope, constraints, and success criteria "
        f"before commercial sign-off."
    )
    combined = (base + filler).strip()
    if len(combined) < _MIN_PROJECT_VISION:
        combined = (combined + " " + filler).strip()
    return combined[:8000]


def _default_tech_stack(items: List[Dict[str, Any]], report: Dict[str, Any]) -> str:
    blob = _join_item_texts(items).lower()
    found: List[str] = []
    seen = set()
    for kw in _TECH_KEYWORDS:
        if kw in blob and kw not in seen:
            found.append(kw)
            seen.add(kw)
        if len(found) >= 12:
            break
    if found:
        return (
            "Technologies and platforms referenced in the parsed document or extraction items: "
            + ", ".join(found)
            + ". Confirm stack, versions, and hosting with your engineering leads."
        )
    rep_hint = ""
    ctx = (report or {}).get("contextDetection") or {}
    if isinstance(ctx, dict):
        bits = [str(v) for v in ctx.values() if v]
        rep_hint = " ".join(bits)
    base = (
        "Integration and technology scope will be refined from the uploaded document. "
        "List languages, frameworks, cloud providers, data stores, and third-party systems."
    )
    if rep_hint and len(base + rep_hint) >= _MIN_TECH_STACK:
        return (base + " Parser context signals: " + rep_hint)[:8000]
    return base


def build_business_context_seed(
    items: List[Dict[str, Any]],
    report: Dict[str, Any],
    *,
    title: str,
    client: str,
) -> Dict[str, Any]:
    """Structured businessContext dict (camelCase) aligned with commercial_validation + wizard_shape_adapter."""
    obj_items = [i for i in items if i.get("category") == ExtractionCategory.business_objectives.value]
    uc_items = [i for i in items if i.get("category") == ExtractionCategory.user_context.value]
    risk_items = [i for i in items if i.get("category") == ExtractionCategory.risk.value]
    feat_items = [i for i in items if i.get("category") == ExtractionCategory.features.value]

    objectives: List[Dict[str, str]] = []
    for i, it in enumerate(obj_items[:8]):
        txt = (it.get("text") or "").strip()[:2000]
        if not txt:
            continue
        objectives.append(
            {
                "objective": txt[:500],
                "measurableTarget": "",
                "timeline": "",
            }
        )

    pain_points: List[Dict[str, str]] = []
    for it in risk_items + uc_items:
        txt = (it.get("text") or "").strip()
        if not txt or len(pain_points) >= 8:
            continue
        pain_points.append(
            {
                "problem": txt[:500],
                "whoExperiences": "Users and stakeholders described in the document",
            }
        )

    profiles: List[Dict[str, Any]] = []
    for it in uc_items[:5]:
        txt = (it.get("text") or "").strip()
        if not txt:
            continue
        profiles.append(
            {
                "roleName": "End user / stakeholder",
                "count": "1",
                "techLiteracy": "Medium",
                "primaryDevice": "Web / desktop",
            }
        )

    vision_source = _join_item_texts(
        obj_items + feat_items + [i for i in items if i.get("category") == ExtractionCategory.assumptions.value]
    )
    if not vision_source.strip():
        vision_source = _join_item_texts(items)

    project_vision = _pad_vision(vision_source, title=title, client=client)

    ctx = (report or {}).get("contextDetection") or {}
    bo_status = (ctx.get("businessObjectives") or "ABSENT") if isinstance(ctx, dict) else "ABSENT"
    criticality = "business_important" if str(bo_status).upper() == "PRESENT" else "standard"

    current = _join_item_texts(risk_items + uc_items)[:2000] or (
        f"Current systems and constraints are described in the uploaded document for {client}."
    )
    desired = _join_item_texts(feat_items + obj_items)[:2000] or (
        "Achieve the business outcomes and delivery scope captured in reviewed extraction items and this SOW."
    )
    success = (
        _join_item_texts(obj_items)[:1500]
        or "Successful delivery when scope is met, stakeholders accept UAT, and operational handover is complete."
    )

    out: Dict[str, Any] = {
        "projectVision": project_vision,
        "businessCriticality": criticality,
        "currentState": current[:4000],
        "desiredFutureState": desired[:4000],
        "definitionOfSuccess": success[:4000],
    }
    if objectives:
        out["businessObjectives"] = objectives
    if pain_points:
        out["painPoints"] = pain_points
    if profiles:
        out["endUserProfiles"] = profiles
    return out


def build_tech_integrations_seed(items: List[Dict[str, Any]], report: Dict[str, Any]) -> Dict[str, Any]:
    return {"technologyStack": _default_tech_stack(items, report)}


def merge_gap_fill_section(seed: Dict[str, Any], existing: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Fill only missing or empty keys in existing from seed (user/PATCH values win when set)."""
    cur = dict(existing or {})
    for key, val in seed.items():
        if key not in cur or _is_empty(cur[key]):
            cur[key] = val
    return cur


def merge_commercial_details_prefill(
    existing: Optional[Dict[str, Any]],
    seed_bc: Dict[str, Any],
    seed_ti: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge prefill seeds into commercial_details without overwriting user-supplied fields."""
    cd = dict(existing or {})
    cd["businessContext"] = merge_gap_fill_section(seed_bc, cd.get("businessContext"))
    cd["techIntegrations"] = merge_gap_fill_section(seed_ti, cd.get("techIntegrations"))
    return cd


def commercial_needs_prefill(commercial_details: Optional[Dict[str, Any]]) -> bool:
    """True if key AI fields are missing so we should apply extraction-based prefill."""
    cd = commercial_details or {}
    bc = cd.get("businessContext") or {}
    ti = cd.get("techIntegrations") or {}
    pv = bc.get("projectVision") or ""
    ts = ti.get("technologyStack") or ""
    return len(str(pv).strip()) < _MIN_PROJECT_VISION or len(str(ts).strip()) < _MIN_TECH_STACK


def build_commercial_prefill_from_extraction(
    items: List[Dict[str, Any]],
    report: Dict[str, Any],
    *,
    title: str,
    client: str,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    return (
        build_business_context_seed(items, report, title=title, client=client),
        build_tech_integrations_seed(items, report),
    )

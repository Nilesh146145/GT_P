"""Commercial details validation (spec §14.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from app.schemas.manual_sow.enums import CommercialSectionKey, CommercialSectionStatus
from app.schemas.manual_sow.manual_sow_platform_type import ManualSowPlatformType, normalize_manual_sow_platform_type


def _non_empty(v: Any) -> bool:
    return v is not None and str(v).strip() != ""


# Belongs only under ``deliveryScope``. If a client PATCHes them into ``businessContext``, remove them
# so the API does not return duplicate platform / scope data in two places.
_DELIVERY_SCOPE_ONLY_KEYS = frozenset(
    {
        "platformType",
        "platform_type",
        "developmentScope",
        "development_scope",
        "uiuxDesignScope",
        "uiux_design_scope",
        "deploymentScope",
        "deployment_scope",
        "goLiveScope",
        "go_live_scope",
        "dataMigrationScope",
        "data_migration_scope",
    }
)


def strip_delivery_scope_fields_from_business_context(
    bc: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], bool]:
    """
    Drop delivery-scope fields wrongly stored under ``businessContext``.

    Returns ``(cleaned_business_context, did_strip)``.
    """
    src = dict(bc or {})
    out = {k: v for k, v in src.items() if k not in _DELIVERY_SCOPE_ONLY_KEYS}
    return out, len(out) != len(src)


def validate_section(
    section: CommercialSectionKey, data: Dict[str, Any]
) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}
    d = data or {}

    if section == CommercialSectionKey.businessContext:
        pv = d.get("projectVision") or d.get("project_vision") or ""
        if len(str(pv).strip()) < 50:
            errors["projectVision"] = "Must be at least 50 characters"
        bc = d.get("businessCriticality") or d.get("business_criticality")
        allowed_bc = {"mission_critical", "business_important", "standard", "low"}
        if not _non_empty(bc) or str(bc) not in allowed_bc:
            errors["businessCriticality"] = "Must be one of mission_critical, business_important, standard, low"
        for fld, key in [
            ("currentState", "current_state"),
            ("desiredFutureState", "desired_future_state"),
            ("definitionOfSuccess", "definition_of_success"),
        ]:
            v = d.get(fld) or d.get(key)
            if not _non_empty(v):
                errors[fld] = "Must be non-empty"

    elif section == CommercialSectionKey.deliveryScope:
        dev = d.get("developmentScope") or d.get("development_scope") or []
        if not isinstance(dev, list) or len(dev) < 1:
            errors["developmentScope"] = "At least one development scope item required"
        pt = d.get("platformType") or d.get("platform_type")
        allowed_pt = {e.value for e in ManualSowPlatformType}
        pt_norm = normalize_manual_sow_platform_type(pt)
        pt_check = pt_norm if pt_norm else pt
        if not _non_empty(pt_check):
            errors["platformType"] = "Must be set (choose a platform type)"
        elif str(pt_check).strip() not in allowed_pt:
            errors["platformType"] = f"Must be one of {sorted(allowed_pt)}"
        for fld, allowed in [
            ("uiuxDesignScope", ("not_in_scope", "in_scope", "client_provides")),
            ("deploymentScope", ("not_in_scope", "cloud", "on_premise", "both")),
            ("goLiveScope", ("not_in_scope", "go_live", "go_live_hypercare")),
            ("dataMigrationScope", ("not_in_scope", "in_scope")),
        ]:
            v = d.get(fld) or d.get(_snake(fld))
            if not _non_empty(v) or v not in allowed:
                errors[fld] = f"Must be one of {allowed}"

    elif section == CommercialSectionKey.techIntegrations:
        ts = d.get("technologyStack") or d.get("technology_stack") or ""
        if len(str(ts).strip()) < 10:
            errors["technologyStack"] = "Must be at least 10 characters"

    elif section == CommercialSectionKey.timelineTeam:
        sd = d.get("startDate") or d.get("start_date")
        ed = d.get("targetEndDate") or d.get("target_end_date")
        if not _non_empty(sd):
            errors["startDate"] = "Must be a non-empty ISO 8601 date"
        if not _non_empty(ed):
            errors["targetEndDate"] = "Must be a non-empty ISO 8601 date"
        if sd and ed:
            try:
                sdt = datetime.fromisoformat(str(sd).replace("Z", "+00:00"))
                edt = datetime.fromisoformat(str(ed).replace("Z", "+00:00"))
                if edt <= sdt:
                    errors["targetEndDate"] = "Must be strictly after startDate"
            except ValueError:
                errors["targetEndDate"] = "Invalid date format"
        uat_a = d.get("uatSignOffAuthority") or d.get("uat_sign_off_authority")
        if not _non_empty(uat_a):
            errors["uatSignOffAuthority"] = "Must be non-empty"
        if d.get("uatSignOffConfirmed") is not True and d.get("uat_sign_off_confirmed") is not True:
            errors["uatSignOffConfirmed"] = "Must be true"

    elif section == CommercialSectionKey.budgetRisk:
        bmin = d.get("budgetMinimum", d.get("budget_minimum"))
        bmax = d.get("budgetMaximum", d.get("budget_maximum"))
        try:
            bmin_f = float(bmin)
            bmax_f = float(bmax)
            if bmin_f <= 0:
                errors["budgetMinimum"] = "Must be > 0"
            if bmax_f <= 0:
                errors["budgetMaximum"] = "Must be > 0"
            if bmax_f < bmin_f:
                errors["budgetMaximum"] = "Must be >= budgetMinimum"
        except (TypeError, ValueError):
            errors["budgetMinimum"] = "Valid budget numbers required"
        pm = d.get("pricingModel") or d.get("pricing_model")
        allowed_p = {"fixed_price", "time_and_materials", "outcome_based", "hybrid"}
        if not _non_empty(pm) or pm not in allowed_p:
            errors["pricingModel"] = f"Must be one of {allowed_p}"

    elif section == CommercialSectionKey.governance:
        if d.get("nonDiscriminationConfirmed") is not True and d.get("non_discrimination_confirmed") is not True:
            errors["nonDiscriminationConfirmed"] = "Must be true"
        dsl = d.get("dataSensitivityLevel") or d.get("data_sensitivity_level")
        allowed_ds = {"public", "internal", "confidential", "restricted"}
        if not _non_empty(dsl) or dsl not in allowed_ds:
            errors["dataSensitivityLevel"] = f"Must be one of {allowed_ds}"
        pdi = d.get("personalDataInvolved") or d.get("personal_data_involved")
        if pdi not in ("yes", "no"):
            errors["personalDataInvolved"] = "Must be yes or no"

    elif section == CommercialSectionKey.commercialLegal:
        for fld, allowed in [
            ("ipOwnership", ("client_owns_all", "glimmora_retains_framework", "joint", "custom")),
            ("sourceCodeOwnership", ("client_hosts", "glimmora_hosts_transfer", "client_provides_day_one")),
            ("changeRequestProcess", ("formal_cr", "threshold_cr", "time_and_materials")),
            ("thirdPartyCosts", ("client_pays", "glimmora_absorbs", "split")),
        ]:
            v = d.get(fld) or d.get(_snake(fld))
            if not _non_empty(v) or v not in allowed:
                errors[fld] = f"Must be one of {allowed}"

    return (len(errors) == 0, errors)


def _snake(name: str) -> str:
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def validate_approvers(authorities: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}
    bo = (authorities or {}).get("business_owner_approver") or (authorities or {}).get("businessOwnerApprover")
    fa = (authorities or {}).get("final_approver") or (authorities or {}).get("finalApprover")
    if not _non_empty(bo):
        errors["business_owner_approver"] = "Required"
    if not _non_empty(fa):
        errors["final_approver"] = "Required"
    return (len(errors) == 0, errors)


def all_sections_complete(section_status: Dict[str, str]) -> bool:
    keys = {e.value for e in CommercialSectionKey}
    for k in keys:
        if section_status.get(k) != "complete":
            return False
    return True


def promote_prerequisite_sections_when_valid(
    section_status: Optional[Dict[str, Any]],
    commercial_details: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """
    After PATCH / extraction prefill: mark businessContext and deliveryScope as complete when
    validate_section passes so Tech & Integrations AI can run without a separate mark-complete call.
    """
    cd = commercial_details or {}
    out = dict(section_status or {})
    for key in (CommercialSectionKey.businessContext, CommercialSectionKey.deliveryScope):
        data = cd.get(key.value) or {}
        ok, _ = validate_section(key, data)
        if ok:
            out[key.value] = CommercialSectionStatus.complete.value
    return out


def downgrade_prerequisite_sections_if_invalid(
    section_status: Optional[Dict[str, Any]],
    commercial_details: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """
    On GET commercial-details: if a section was complete but data no longer validates, drop to in_progress.
    """
    cd = commercial_details or {}
    out = dict(section_status or {})
    for key in (CommercialSectionKey.businessContext, CommercialSectionKey.deliveryScope):
        data = cd.get(key.value) or {}
        ok, _ = validate_section(key, data)
        prev = out.get(key.value)
        if not ok and prev == CommercialSectionStatus.complete.value:
            out[key.value] = CommercialSectionStatus.in_progress.value
    return out


def ai_tech_stack_generation_ready(
    section_status: Optional[Dict[str, Any]],
    commercial_details: Optional[Dict[str, Any]],
) -> Tuple[bool, Dict[str, str]]:
    """
    Tech-stack AI runs only when Section A and B data validate AND both are marked complete
    (completion is set automatically when validation passes on PATCH / prefill / extraction).
    """
    cd = commercial_details or {}
    ok_pre, _ = tech_integrations_prerequisites(cd)
    if not ok_pre:
        return False, {}
    ss = section_status or {}
    hints: Dict[str, str] = {}
    ready = True
    bc = ss.get(CommercialSectionKey.businessContext.value)
    ds = ss.get(CommercialSectionKey.deliveryScope.value)
    if bc != CommercialSectionStatus.complete.value:
        ready = False
        hints["businessContext"] = (
            "Finish Business Context (all required fields); it must show as complete before AI fills Tech & Integrations."
        )
    if ds != CommercialSectionStatus.complete.value:
        ready = False
        hints["deliveryScope"] = (
            "Finish Delivery Scope, including platform type and scope enums; it must show as complete before AI runs."
        )
    return ready, hints


def tech_integrations_prerequisites(
    commercial_details: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Dict[str, Dict[str, str]]]:
    """
    Section C (techIntegrations) should be offered only after Section A (businessContext)
    and Section B (deliveryScope) satisfy required-field validation.
    """
    cd = commercial_details or {}
    bc = cd.get("businessContext") or {}
    ds = cd.get("deliveryScope") or {}
    ok_bc, err_bc = validate_section(CommercialSectionKey.businessContext, bc)
    ok_ds, err_ds = validate_section(CommercialSectionKey.deliveryScope, ds)
    errors: Dict[str, Dict[str, str]] = {}
    if not ok_bc:
        errors["businessContext"] = err_bc
    if not ok_ds:
        errors["deliveryScope"] = err_ds
    return (ok_bc and ok_ds, errors)

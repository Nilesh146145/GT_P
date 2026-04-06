"""Commercial details validation (spec §14.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple

from app.schemas.manual_sow.enums import CommercialSectionKey


def _non_empty(v: Any) -> bool:
    return v is not None and str(v).strip() != ""


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
            ("warrantyPeriod", ("30_days", "60_days", "90_days", "6_months", "custom", "none")),
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

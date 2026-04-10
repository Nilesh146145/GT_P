"""
Map Manual SOW commercial details + metadata into wizard step dicts
expected by sow_generator.generate_sow_content / run_hallucination_checks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.schemas.common import Industry, PlatformType, ProjectCategory


def _get_section(commercial: Dict[str, Any], key: str) -> Dict[str, Any]:
    return commercial.get(key) or {}


def _ip_map(v: Optional[str]) -> str:
    m = {
        "client_owns_all": "Client owns all IP and source code",
        "glimmora_retains_framework": "GlimmoraTeam retains framework and component IP — client owns application layer",
        "joint": "Joint ownership (defined in NDA)",
        "custom": "Custom arrangement",
    }
    return m.get(v or "", "Client owns all IP and source code")


def _repo_map(v: Optional[str]) -> str:
    m = {
        "client_hosts": "Client owns and hosts the repository throughout delivery",
        "glimmora_hosts_transfer": "GlimmoraTeam hosts during delivery, transfers to client on M3 payment",
        "client_provides_day_one": "Client provides repository from day one",
    }
    return m.get(v or "", "Client provides repository from day one")


def _portfolio_map(v: Optional[str]) -> str:
    m = {
        "with_name": "GlimmoraTeam may reference this project as portfolio work with client name",
        "without_name": "GlimmoraTeam may reference this project without disclosing client name",
        "no_reference": "No reference rights (strict NDA)",
    }
    return m.get(v or "", "No reference rights (strict NDA)")


def _third_party_map(v: Optional[str]) -> str:
    m = {
        "client_pays": "Client pays all third-party service and licence costs directly",
        "glimmora_absorbs": "GlimmoraTeam absorbs all within project quote",
        "split": "Split — GlimmoraTeam absorbs up to threshold, client pays above",
    }
    return m.get(v or "", "Client pays all third-party service and licence costs directly")


def _cr_model_map(v: Optional[str]) -> str:
    m = {
        "formal_cr": "All changes formally priced and approved before work begins",
        "threshold_cr": "Changes up to threshold included in contingency — above requires formal CR",
        "time_and_materials": "T&M for all changes above agreed baseline",
    }
    return m.get(v or "", "All changes formally priced and approved before work begins")


def _pricing_map(v: Optional[str]) -> str:
    m = {
        "fixed_price": "Fixed price",
        "time_and_materials": "Time and materials",
        "outcome_based": "Outcome-based",
        "hybrid": "Hybrid",
    }
    return m.get(v or "", "Fixed price")


def _personal_bool(v: Optional[str]) -> bool:
    return (v or "").lower() == "yes"


def _sensitivity_title(s: Optional[str]) -> str:
    """Map manual public/internal to wizard DataSensitivity display strings."""
    m = {
        "public": "Public",
        "internal": "Internal",
        "confidential": "Confidential",
        "restricted": "Restricted",
    }
    return m.get(s or "", "Internal")


def build_wizard_data_from_manual(
    *,
    title: str,
    client: str,
    commercial_details: Dict[str, Any],
    feature_module_texts: List[str],
    industry_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    commercial_details keys: businessContext, deliveryScope, techIntegrations,
    timelineTeam, budgetRisk, governance, commercialLegal (camelCase per API).
    """
    bc = _get_section(commercial_details, "businessContext")
    ds = _get_section(commercial_details, "deliveryScope")
    ti = _get_section(commercial_details, "techIntegrations")
    tt = _get_section(commercial_details, "timelineTeam")
    br = _get_section(commercial_details, "budgetRisk")
    gov = _get_section(commercial_details, "governance")
    cl = _get_section(commercial_details, "commercialLegal")

    objectives = bc.get("businessObjectives") or []
    biz_objs = []
    for o in objectives:
        if isinstance(o, dict):
            biz_objs.append(
                {
                    "objective": o.get("objective", ""),
                    "measurable_target": o.get("measurableTarget", o.get("measurable_target", "")),
                    "target_timeline": o.get("timeline", o.get("target_timeline", "")),
                }
            )

    pain_points_raw = bc.get("painPoints") or []
    pain_points = []
    for p in pain_points_raw:
        if isinstance(p, dict):
            pain_points.append(
                {
                    "problem_description": p.get("problem", p.get("problem_description", "")),
                    "who_experiences_it": p.get("whoExperiences", p.get("who_experiences_it", "")),
                }
            )

    end_users = bc.get("endUserProfiles") or []
    profiles = []
    for u in end_users:
        if isinstance(u, dict):
            profiles.append(
                {
                    "role_name": u.get("roleName", u.get("role_name", "User")),
                    "approximate_user_count": str(u.get("count", u.get("approximate_user_count", "1"))),
                    "age_range": "36–55",
                    "tech_literacy": u.get("techLiteracy", "Medium"),
                    "primary_device": u.get("primaryDevice", "Desktop"),
                    "geography": "Global",
                    "accessibility_needs": "No",
                }
            )

    modules: List[Dict[str, str]] = []
    for i, text in enumerate(feature_module_texts[:20]):
        modules.append(
            {
                "module_name": f"Capability {i + 1}",
                "description": text[:300],
                "priority": "Must Have",
            }
        )
    while len(modules) < 2:
        modules.append(
            {
                "module_name": "Core delivery",
                "description": "As defined in reviewed extraction and commercial details.",
                "priority": "Must Have",
            }
        )

    dev_list = ds.get("developmentScope") or ds.get("development_scope") or ["Backend", "Integration"]
    if isinstance(dev_list, str):
        dev_list = [dev_list]

    def _dev_scope_dict(labels: List[str]) -> Dict[str, bool]:
        joined = " ".join(labels).lower()
        scope = {
            "frontend": "front" in joined,
            "backend": "back" in joined or "backend" in joined,
            "api": "api" in joined,
            "database_design": "database" in joined or "data" in joined,
            "third_party_integration": "integration" in joined,
            "ci_cd_setup": "ci/cd" in joined or "cicd" in joined or "ci cd" in joined,
        }
        if not any(scope.values()):
            scope["backend"] = True
        return scope

    dev_scope = _dev_scope_dict([str(x) for x in dev_list])
    exclusions = [f"Out of scope: anything not listed under development scope ({', '.join(str(x) for x in dev_list)})."]

    ui_key = ds.get("uiuxDesignScope") or ds.get("ui_ux_design_scope") or "not_in_scope"
    ui_label = {
        "not_in_scope": "Not in scope",
        "in_scope": "In scope",
        "client_provides": "Client provides designs",
    }.get(ui_key, "Not in scope")

    dep_key = ds.get("deploymentScope") or ds.get("deployment_scope") or "not_in_scope"
    dep_label = {
        "not_in_scope": "Not in scope — working build handover only",
        "cloud": "Deploy to cloud",
        "on_premise": "Deploy to client on-premise",
        "both": "Both",
    }.get(dep_key, "Not in scope — working build handover only")

    gl_key = ds.get("goLiveScope") or ds.get("go_live_scope") or "not_in_scope"
    gl_label = {
        "not_in_scope": "Not in scope",
        "go_live": "Production go-live included",
        "go_live_hypercare": "Go-live + post-go-live hypercare",
    }.get(gl_key, "Not in scope")

    integrations = ti.get("thirdPartyIntegrations") or []
    step3_integrations = []
    for it in integrations[:15]:
        if not isinstance(it, dict):
            continue
        step3_integrations.append(
            {
                "integration_name": it.get("name", "Integration"),
                "direction": "Bidirectional",
                "protocol": "REST",
                "authentication": "API Key",
                "data_format": "JSON",
                "sandbox_credentials_by": "Client",
                "testing_responsibility": "Joint",
                "error_handling_sla": "Same-day",
            }
        )

    milestones_raw = tt.get("milestones") or []
    milestones = []
    for m in milestones_raw:
        if isinstance(m, dict):
            milestones.append(
                {
                    "name": m.get("name", ""),
                    "target_date": m.get("targetDate", m.get("target_date", "")),
                    "acceptance_criteria": m.get("acceptanceCriteria", m.get("acceptance_criteria", "")),
                }
            )

    known_risks_raw = br.get("knownRisks") or []
    known_risks = []
    for r in known_risks_raw:
        if isinstance(r, dict):
            known_risks.append(
                {
                    "description": r.get("description", ""),
                    "likelihood": r.get("likelihood", "Medium"),
                    "impact": r.get("impact", "Medium"),
                }
            )

    privacy_laws = gov.get("applicablePrivacyLaw") or gov.get("applicable_privacy_law") or []
    if isinstance(privacy_laws, str):
        privacy_laws = [privacy_laws]

    dpa = gov.get("dpaRequired") or gov.get("dpa_required") or "no"
    dpa_map = {"yes": "Yes", "no": "No", "already_in_place": "Already in place"}

    step_0: Dict[str, Any] = {
        "section_a": {
            "project_vision": bc.get("projectVision") or bc.get("project_vision") or "",
            "business_objectives": biz_objs,
            "pain_points": pain_points,
            "strategic_context": "Digital transformation",
            "business_criticality": (bc.get("businessCriticality") or "standard").replace("_", " ").title(),
        },
        "section_b": {
            "current_state_not_applicable": False,
            "current_state_description": bc.get("currentState") or bc.get("current_state") or "",
            "desired_future_state": bc.get("desiredFutureState") or bc.get("desired_future_state") or "",
            "previous_attempts": "",
        },
        "section_c": {
            "end_user_profiles": profiles or [{"role_name": "End user", "approximate_user_count": "1", "age_range": "18–35", "tech_literacy": "Medium", "primary_device": "Desktop", "geography": "Global", "accessibility_needs": "No"}],
            "languages": ["English"],
            "translation_provider": "Client provides translated strings",
            "user_expectations": [],
        },
    }

    step_1: Dict[str, Any] = {
        "section_a": {
            "project_title": title,
            "client_organisation": client,
            "industry": Industry.other.value,
            "industry_other": industry_hint or "General",
            "project_category": ProjectCategory.feature_expansion.value,
            "platform_type": PlatformType.web_app.value,
            "platform_other": None,
            "client_tech_landscape": ti.get("technologyStack") or "",
        },
        "section_b": {
            "feature_modules": modules,
            "user_roles": [{"role_name": "User", "primary_actions": "Use the system"}],
            "key_workflows": [{"workflow_name": "Primary", "steps": [{"step_number": 1, "description": "Execute"}], "outcome": "Success"}],
        },
        "section_c": {"out_of_scope_exclusions": exclusions},
    }

    success_metrics_raw = bc.get("successMetrics") or bc.get("success_metrics") or []
    success_metrics = []
    for m in success_metrics_raw:
        if isinstance(m, dict):
            success_metrics.append(
                {
                    "metric_name": m.get("metricName", m.get("metric_name", "")),
                    "baseline_value": m.get("baseline", m.get("baseline_value", "")),
                    "target_value": m.get("target", m.get("target_value", "")),
                    "measurement_method": m.get("method", m.get("measurement_method", "")),
                    "timeframe": m.get("timeframe", ""),
                }
            )

    step_0["section_d"] = {
        "definition_of_success": bc.get("definitionOfSuccess") or bc.get("definition_of_success") or "",
        "success_metrics": success_metrics,
    }

    step_2: Dict[str, Any] = {
        "section_a": {
            "development_scope": dev_scope,
            "ui_ux": {"scope": ui_label},
            "deployment": {"scope": dep_label},
            "go_live": {
                "scope": gl_label,
                "hypercare_duration": ds.get("hypercareDuration"),
            },
        },
        "section_b": {
            "technology_stack": ti.get("technologyStack") or ti.get("technology_stack") or "Not specified",
        },
        "section_c": {},
    }

    step_3: Dict[str, Any] = {
        # Must be a list (possibly empty); never None — compute_confidence score_step_3 calls len(integrations).
        "section_a": {"integrations": list(step3_integrations or [])},
        "section_b": {
            "sso_required": bool(ti.get("ssoRequired")),
            "sso_provider_name": None,
            "sso_protocol": None,
            "user_registration_model": None,
        },
    }

    uat_auth = tt.get("uatSignOffAuthority") or tt.get("uat_sign_off_authority") or ""

    step_4: Dict[str, Any] = {
        "section_a": {
            "start_date": tt.get("startDate") or tt.get("start_date"),
            "target_end_date": tt.get("targetEndDate") or tt.get("target_end_date"),
            "phasing_strategy": tt.get("phasingStrategy") or tt.get("phasing_strategy") or "",
            "key_milestones": milestones,
        },
        "section_b": {
            "estimated_team_size": tt.get("estimatedTeamSize") or "4-8",
            "work_model": tt.get("workModel") or "hybrid",
        },
        "section_c": {
            "uat": {
                "signoff_authority_name": uat_auth,
                "signoff_authority_title": uat_auth,
                "uat_duration_days": str(tt.get("uatDuration") or "14"),
                "glimmora_support_level": "Standard",
            }
        },
    }

    step_5: Dict[str, Any] = {
        "section_a": {
            "budget_minimum": br.get("budgetMinimum"),
            "budget_maximum": br.get("budgetMaximum"),
            "currency": br.get("currency") or "USD",
            "pricing_model": _pricing_map(br.get("pricingModel")),
        },
        "section_b": {
            "known_risks": known_risks,
            "contingency_budget": br.get("contingencyPercent") or "10",
            "escalation_process": "Standard escalation",
        },
    }

    step_6: Dict[str, Any] = {
        "project_level_acceptance_criteria": "Deliverables meet agreed acceptance criteria per milestone.",
        "browser_compatibility": {"chrome": True, "firefox": True, "safari": True, "edge": True, "ie11": False, "all_modern": False},
        "device_compatibility": {"desktop": True, "tablet": True, "mobile": True, "kiosk_pos": False},
    }

    personal = _personal_bool(gov.get("personalDataInvolved") or gov.get("personal_data_involved"))
    step_7: Dict[str, Any] = {
        "section_a": {
            "non_discrimination_confirmed": bool(gov.get("nonDiscriminationConfirmed")),
            "labour_standards": "Local jurisdiction regulations",
            "accessibility_requirements": "WCAG 2.1 Level AA",
            "prohibited_work_categories": [],
        },
        "section_b": {
            "personal_data_involved": personal,
            "personal_data_detail": (
                {
                    "data_categories": ["Business contact"],
                    "applicable_privacy_laws": privacy_laws or ["GDPR"],
                    "dpa_required": dpa_map.get(str(dpa).lower().replace(" ", "_"), "No"),
                }
                if personal
                else None
            ),
        },
        "section_c": {
            "data_sensitivity_level": _sensitivity_title(gov.get("dataSensitivityLevel")),
            "regulatory_frameworks": gov.get("regulatoryFrameworks") or [],
            "data_residency": gov.get("dataResidency") or "No restriction",
            "access_control_model": "RBAC",
        },
    }

    cr_approver = cl.get("changeRequestApprover") or cl.get("change_request_approver") or ""

    step_8: Dict[str, Any] = {
        "section_a": {
            "ip_ownership": _ip_map(cl.get("ipOwnership")),
            "source_code_repo_ownership": _repo_map(cl.get("sourceCodeOwnership")),
            "portfolio_reference_rights": _portfolio_map(cl.get("portfolioReferenceRights")),
            "oss_policy": "Client accepts OSS components with compatible licences (MIT, Apache, BSD)",
        },
        "section_b": {
            "third_party_licensing": _third_party_map(cl.get("thirdPartyCosts")),
            "warranty_period": "Handled via master commercial agreement",
            "change_request_process": {
                "model": _cr_model_map(cl.get("changeRequestProcess")),
                "approver_name": cr_approver,
                "approver_role": "",
            },
        },
    }

    return {
        "step_0": step_0,
        "step_1": step_1,
        "step_2": step_2,
        "step_3": step_3,
        "step_4": step_4,
        "step_5": step_5,
        "step_6": step_6,
        "step_7": step_7,
        "step_8": step_8,
    }


def steps_completed_for_manual() -> List[int]:
    """Treat mandatory wizard steps as satisfied once commercial form is complete."""
    return [0, 1, 2, 3, 4, 5, 6, 7, 8]

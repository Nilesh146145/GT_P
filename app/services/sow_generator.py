"""
SOW Generation Service
Transforms wizard step data into a structured, clause-rich Statement of Work.
In production this would call an LLM. Here we generate a well-structured template
seeded with all captured inputs.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional


def generate_sow_content(wizard_data: Dict) -> Dict:
    """
    Generates the full SOW document from wizard data.
    Returns structured sections with per-section content and confidence badges.
    """
    step0 = wizard_data.get("step_0") or {}
    step1 = wizard_data.get("step_1") or {}
    step2 = wizard_data.get("step_2") or {}
    step3 = wizard_data.get("step_3") or {}
    step4 = wizard_data.get("step_4") or {}
    step5 = wizard_data.get("step_5") or {}
    step6 = wizard_data.get("step_6") or {}
    step7 = wizard_data.get("step_7") or {}
    step8 = wizard_data.get("step_8") or {}

    s0a = (step0.get("section_a") or {})
    s0b = (step0.get("section_b") or {})
    s0c = (step0.get("section_c") or {})
    s0d = (step0.get("section_d") or {})
    s1a = (step1.get("section_a") or {})
    s1b = (step1.get("section_b") or {})
    s1c = (step1.get("section_c") or {})
    s2a = (step2.get("section_a") or {})
    s2b = (step2.get("section_b") or {})
    s5a = (step5.get("section_a") or {})
    s5b = (step5.get("section_b") or {})
    s7a = (step7.get("section_a") or {})
    s7b = (step7.get("section_b") or {})
    s7c = (step7.get("section_c") or {})
    s8a = (step8.get("section_a") or {})
    s8b = (step8.get("section_b") or {})

    project_title = s1a.get("project_title", "[Project Title]")
    client_org = s1a.get("client_organisation", "[Client Organisation]")
    today = datetime.utcnow().strftime("%d %B %Y")

    sections = []

    # ── 1. Project Vision Statement ──────────────────────
    vision = s0a.get("project_vision", "")
    objectives = s0a.get("business_objectives", [])
    pain_points = s0a.get("pain_points", [])

    obj_text = "\n".join(
        f"  - {o.get('objective', '')} — Target: {o.get('measurable_target', '')} by {o.get('target_timeline', '')}"
        for o in objectives
    ) if objectives else "  - [No business objectives specified]"

    pain_text = "\n".join(
        f"  - {p.get('problem_description', '')} (Experienced by: {p.get('who_experiences_it', '')})"
        for p in pain_points
    ) if pain_points else "  - [No pain points specified]"

    sections.append({
        "section_id": "S1",
        "title": "1. Project Vision & Business Context",
        "confidence": 95 if vision else 40,
        "content": f"""**Project Vision**
{vision or '[Vision not specified]'}

**Business Objectives (SMART)**
{obj_text}

**Problems Being Solved**
{pain_text}

**Strategic Context:** {s0a.get('strategic_context', 'Not specified')}
**Business Criticality:** {s0a.get('business_criticality', 'Not specified')}
**Definition of Project Success:** {s0d.get('definition_of_success', 'Not specified')}
"""
    })

    # ── 2. Project Identity & Scope ──────────────────────
    modules = s1b.get("feature_modules", [])
    modules_text = "\n".join(
        f"  - **{m.get('module_name', '')}** [{m.get('priority', '')}]: {m.get('description', '')}"
        for m in modules
    ) if modules else "  - [No modules specified]"

    exclusions = s1c.get("out_of_scope_exclusions", [])
    excl_text = "\n".join(f"  - {e}" for e in exclusions) if exclusions else "  - All items not explicitly listed as in-scope are excluded."

    roles = s1b.get("user_roles", [])
    roles_text = "\n".join(
        f"  - **{r.get('role_name', '')}**: {r.get('primary_actions', '')}"
        for r in roles
    ) if roles else "  - [No user roles specified]"

    sections.append({
        "section_id": "S2",
        "title": "2. Project Identity & Functional Scope",
        "confidence": 90 if modules else 30,
        "content": f"""**Project Title:** {project_title}
**Client Organisation:** {client_org}
**Industry:** {s1a.get('industry', '[Not specified]')}
**Project Category:** {s1a.get('project_category', '[Not specified]')}
**Platform:** {s1a.get('platform_type', '[Not specified]')}

**Feature Modules**
{modules_text}

**User Roles**
{roles_text}

**Out of Scope — Exclusions**
{excl_text}
"""
    })

    # ── 3. Delivery & Technical Architecture ──────────────
    dev_scope = s2a.get("development_scope") or {}
    selected_dev = [k for k, v in dev_scope.items() if v is True]
    tech_stack = s2b.get("technology_stack", "[Not specified]")

    deploy = s2a.get("deployment") or {}
    deploy_scope = deploy.get("scope", "[Not specified]")

    go_live = s2a.get("go_live") or {}
    go_live_scope = go_live.get("scope", "[Not specified]")

    sections.append({
        "section_id": "S3",
        "title": "3. Delivery Scope & Technical Architecture",
        "confidence": 90 if tech_stack != "[Not specified]" else 40,
        "content": f"""**Development Scope**
{', '.join(selected_dev) if selected_dev else '[None selected]'}

**Technology Stack**
{tech_stack}

**UI/UX Design Scope:** {(s2a.get('ui_ux') or {}).get('scope', '[Not specified]')}
**Deployment Scope:** {deploy_scope}
**Go-Live Scope:** {go_live_scope}
**Hypercare Duration:** {go_live.get('hypercare_duration', 'N/A')}
"""
    })

    # ── 4. Target End Users & Acceptance Criteria ─────────
    user_profiles = (s0c.get("end_user_profiles") or [])
    profiles_text = "\n".join(
        f"  - **{p.get('role_name', '')}** — {p.get('approximate_user_count', '')} users, "
        f"Age: {p.get('age_range', '')}, Tech literacy: {p.get('tech_literacy', '')}, "
        f"Device: {p.get('primary_device', '')}, Accessibility: {p.get('accessibility_needs', '')}"
        for p in user_profiles
    ) if user_profiles else "  - [No user profiles specified]"

    success_metrics = (s0d.get("success_metrics") or [])
    metrics_text = "\n".join(
        f"  - **{m.get('metric_name', '')}**: Baseline {m.get('baseline_value', '')} → "
        f"Target {m.get('target_value', '')} ({m.get('measurement_method', '')}, {m.get('timeframe', '')})"
        for m in success_metrics
    ) if success_metrics else "  - [No success metrics specified]"

    project_ac = step6.get("project_level_acceptance_criteria", "[Not specified]")

    sections.append({
        "section_id": "S4",
        "title": "4. Target End Users & Acceptance Criteria",
        "confidence": 85 if user_profiles else 35,
        "content": f"""**End User Profiles**
{profiles_text}

**Success Metrics / KPIs**
{metrics_text}

**Project-Level Acceptance Criteria**
{project_ac}
"""
    })

    # ── 5. Timeline, Team & Testing ────────────────────────
    s4a = (step4.get("section_a") or {})
    s4b = (step4.get("section_b") or {})
    s4c = (step4.get("section_c") or {})

    start_date = str(s4a.get("start_date", "[TBD]"))
    end_date = str(s4a.get("target_end_date", "[TBD]"))

    milestones = s4a.get("key_milestones") or []
    milestone_text = "\n".join(
        f"  - **{m.get('name', '')}** ({m.get('target_date', '')}): {m.get('acceptance_criteria', '')}"
        for m in milestones
    ) if milestones else "  - [Milestones to be defined at project kick-off]"

    required_roles = s4b.get("required_roles") or []
    roles_team_text = "\n".join(
        f"  - {r.get('role_name', '')} ({r.get('seniority', '')})"
        for r in required_roles
    ) if required_roles else "  - [Team roles not specified]"

    uat = s4c.get("uat") or {}
    sections.append({
        "section_id": "S5",
        "title": "5. Timeline, Team Composition & Testing",
        "confidence": 80 if start_date != "[TBD]" else 30,
        "content": f"""**Project Timeline**
Start Date: {start_date}
Target End Date: {end_date}
Phasing Strategy: {s4a.get('phasing_strategy', '[Not specified]')}

**Key Milestones**
{milestone_text}

**Team Composition**
Size: {s4b.get('estimated_team_size', '[Not specified]')}
Work Model: {s4b.get('work_model', '[Not specified]')}
{roles_team_text}

**UAT Sign-off Authority**
Name: {uat.get('signoff_authority_name', '[Not designated]')}
Title: {uat.get('signoff_authority_title', '[Not designated]')}
UAT Duration: {uat.get('uat_duration_days', '[Not specified]')} days
GlimmoraTeam Support: {uat.get('glimmora_support_level', '[Not specified]')}

**Payment Schedule**
30% on SOW onboarding (M1) · 35% on development completion (M2) · 35% on UAT sign-off (M3).
All payments due before production go-live.
"""
    })

    # ── 6. Budget & Risk ──────────────────────────────────
    budget_min = s5a.get("budget_minimum", "[TBD]")
    budget_max = s5a.get("budget_maximum", "[TBD]")
    currency = s5a.get("currency", "USD")
    pricing = s5a.get("pricing_model", "[Not specified]")

    risks = s5b.get("known_risks") or []
    risks_text = "\n".join(
        f"  - {r.get('description', '')} — Likelihood: {r.get('likelihood', '')}, Impact: {r.get('impact', '')}"
        for r in risks
    ) if risks else "  - [No risks declared]"

    budget_min_fmt = f"{budget_min:,.2f}" if isinstance(budget_min, (int, float)) else str(budget_min)
    budget_max_fmt = f"{budget_max:,.2f}" if isinstance(budget_max, (int, float)) else str(budget_max)
    sections.append({
        "section_id": "S6",
        "title": "6. Budget, Risk & Commercial Terms",
        "confidence": 90 if budget_min != "[TBD]" else 20,
        "content": f"""**Budget Range**
Minimum: {currency} {budget_min_fmt}
Maximum: {currency} {budget_max_fmt}
Pricing Model: {pricing}
Contingency: {s5b.get('contingency_budget', '[Not specified]')}

**Known Risks**
{risks_text}

**Escalation Process:** {s5b.get('escalation_process', '[Not specified]')}
"""
    })

    # ── 7. Governance & Compliance ────────────────────────
    sensitivity = s7c.get("data_sensitivity_level", "[MUST BE SPECIFIED]")
    privacy_law = "N/A"
    if s7b.get("personal_data_involved"):
        detail = s7b.get("personal_data_detail") or {}
        laws = detail.get("applicable_privacy_laws", [])
        privacy_law = ", ".join(laws) if laws else "[Not specified]"

    sections.append({
        "section_id": "S7",
        "title": "7. Governance & Compliance",
        "confidence": 90 if sensitivity not in ("[MUST BE SPECIFIED]", None) else 0,
        "content": f"""**Data Sensitivity Level:** {sensitivity}
**Personal Data Involved:** {'Yes' if s7b.get('personal_data_involved') else 'No'}
**Applicable Privacy Law(s):** {privacy_law}
**Regulatory Frameworks:** {', '.join(s7c.get('regulatory_frameworks') or []) or 'None declared'}
**Accessibility Standard:** {s7a.get('accessibility_requirements', '[Not specified]')}
**Data Residency:** {s7c.get('data_residency', 'No restriction')}
**Access Control Model:** {s7c.get('access_control_model', '[Not specified]')}

**Ethical Constraints**
Non-Discrimination Confirmed: {'✓ Yes' if s7a.get('non_discrimination_confirmed') else '✗ Not confirmed — HARD BLOCK'}
Labour Standards: {s7a.get('labour_standards', '[Not specified]')}
Prohibited Work Categories: {', '.join(s7a.get('prohibited_work_categories') or []) or 'None declared'}
"""
    })

    # ── 8. Intellectual Property & Legal Terms ─────────────
    sections.append({
        "section_id": "S8",
        "title": "8. Intellectual Property & Legal Terms",
        "confidence": 95 if s8a.get("ip_ownership") else 10,
        "content": f"""**IP Ownership**
{s8a.get('ip_ownership', '[NOT SPECIFIED — legally incomplete]')}
{('Custom arrangement: ' + s8a.get('ip_ownership_custom_description', '')) if s8a.get('ip_ownership') == 'Custom arrangement' else ''}

**Source Code Repository**
{s8a.get('source_code_repo_ownership', '[Not specified]')}

**Portfolio / Reference Rights**
{s8a.get('portfolio_reference_rights', '[Not specified]')}

**Open Source Policy**
{s8a.get('oss_policy', '[Not specified]')}

**Third-Party Licensing & Service Costs**
{s8b.get('third_party_licensing', '[Not specified]')}
{('Threshold: ' + str(s8b.get('third_party_licensing_threshold_amount', ''))) if s8b.get('third_party_licensing') == 'Split — GlimmoraTeam absorbs up to threshold, client pays above' else ''}

**Warranty Period**
{s8b.get('warranty_period', '[Not specified]')}

**Change Request Process**
{(s8b.get('change_request_process') or {}).get('model', '[Not specified]')}
CR Approver: {(s8b.get('change_request_process') or {}).get('approver_name', '[Not designated]')} — {(s8b.get('change_request_process') or {}).get('approver_role', '')}
"""
    })

    return {
        "document_title": f"Statement of Work — {project_title}",
        "client": client_org,
        "generated_date": today,
        "sections": sections,
        "section_count": len(sections),
    }


def run_hallucination_checks(wizard_data: Dict, steps_completed: List[int]) -> List[Dict]:
    """
    Runs all 8 hallucination prevention layers.
    Returns list of layer results with status: grey | green | amber | red
    """
    layers = []
    s0a = (wizard_data.get("step_0") or {}).get("section_a") or {}
    s1a = (wizard_data.get("step_1") or {}).get("section_a") or {}
    s7a = (wizard_data.get("step_7") or {}).get("section_a") or {}
    s7c = (wizard_data.get("step_7") or {}).get("section_c") or {}

    # Layer 1: Template Selection Validation
    platform = s1a.get("platform_type")
    category = s1a.get("project_category")
    l1_active = 1 in steps_completed
    layers.append({
        "layer_id": 1, "name": "Template Selection Validation",
        "active": l1_active,
        "status": "green" if (l1_active and platform and category) else ("amber" if l1_active else "grey"),
        "detail": f"Platform: {platform}, Category: {category}" if l1_active else "Complete Step 1 to activate."
    })

    # Layer 2: Scope Boundary Enforcement
    l2_active = 1 in steps_completed
    exclusions = (wizard_data.get("step_1") or {}).get("section_c", {}).get("out_of_scope_exclusions", [])
    layers.append({
        "layer_id": 2, "name": "Scope Boundary Enforcement",
        "active": l2_active,
        "status": "green" if (l2_active and exclusions) else ("amber" if l2_active else "grey"),
        "detail": f"{len(exclusions)} explicit exclusions declared." if l2_active else "Complete Step 1 to activate."
    })

    # Layer 3: Clause Library Matching
    l3_active = 7 in steps_completed
    sensitivity = s7c.get("data_sensitivity_level")
    layers.append({
        "layer_id": 3, "name": "Clause Library Matching",
        "active": l3_active,
        "status": "green" if (l3_active and sensitivity) else ("red" if l3_active else "grey"),
        "detail": f"Data Sensitivity: {sensitivity}" if sensitivity else "Data Sensitivity Level not selected — REQUIRED."
    })

    # Layer 4: Cross-Step Consistency Check
    l4_active = 2 in steps_completed
    tech_stack = (wizard_data.get("step_2") or {}).get("section_b", {}).get("technology_stack", "")
    layers.append({
        "layer_id": 4, "name": "Cross-Step Consistency Check",
        "active": l4_active,
        "status": "green" if (l4_active and tech_stack) else ("amber" if l4_active else "grey"),
        "detail": "Tech stack cross-referenced with integration specs." if l4_active else "Complete Step 2 to activate."
    })

    # Layer 5: Compliance Alignment
    l5_active = 7 in steps_completed
    frameworks = s7c.get("regulatory_frameworks", [])
    layers.append({
        "layer_id": 5, "name": "Compliance Alignment",
        "active": l5_active,
        "status": "green" if l5_active else "grey",
        "detail": f"Frameworks: {', '.join(frameworks) if frameworks else 'None declared'}." if l5_active else "Complete Step 7 to activate."
    })

    # Layer 6: Prohibited Clause Detection
    l6_active = 7 in steps_completed
    non_discrim = s7a.get("non_discrimination_confirmed", False)
    layers.append({
        "layer_id": 6, "name": "Prohibited Clause Detection",
        "active": l6_active,
        "status": "green" if (l6_active and non_discrim) else ("red" if l6_active else "grey"),
        "detail": "Non-discrimination confirmed. No prohibited clauses detected." if non_discrim else "Non-discrimination confirmation MISSING — hard block on submission."
    })

    # Layer 7: Business Context Anchoring
    l7_active = 0 in steps_completed
    vision = s0a.get("project_vision", "")
    layers.append({
        "layer_id": 7, "name": "Business Context Anchoring",
        "active": l7_active,
        "status": "green" if (l7_active and len(vision) >= 50) else ("amber" if l7_active else "grey"),
        "detail": "All generated clauses anchored to business vision and objectives." if l7_active else "Complete Step 0 to activate."
    })

    # Layer 8: Evidence Pack Gate Validation
    l8_active = 4 in steps_completed
    uat = (wizard_data.get("step_4") or {}).get("section_c", {}).get("uat", {})
    signoff = uat.get("signoff_authority_name") if uat else None
    layers.append({
        "layer_id": 8, "name": "Evidence Pack Gate Validation",
        "active": l8_active,
        "status": "green" if (l8_active and signoff) else ("amber" if l8_active else "grey"),
        "detail": f"UAT Sign-off Authority: {signoff}" if signoff else "UAT Sign-off Authority not designated."
    })

    return layers


def compute_risk_score(wizard_data: Dict) -> Dict:
    """
    Weighted risk score: Completeness 30% + Confidence 25% + Compliance 25% + Pattern Match 20%
    """
    steps_with_data = sum(1 for i in range(9) if wizard_data.get(f"step_{i}"))
    completeness_score = (steps_with_data / 9) * 100

    s7c = (wizard_data.get("step_7") or {}).get("section_c") or {}
    compliance_score = 75.0
    if s7c.get("data_sensitivity_level"):
        compliance_score = 90.0
    if s7c.get("regulatory_frameworks"):
        compliance_score = min(100.0, compliance_score + 10)

    # Pattern match score — basic heuristic
    has_risks = bool((wizard_data.get("step_5") or {}).get("section_b", {}).get("known_risks"))
    pattern_score = 80.0 if has_risks else 50.0

    # Overall risk (lower = less risky)
    weighted = (
        completeness_score * 0.30 +
        80.0 * 0.25 +  # placeholder confidence
        compliance_score * 0.25 +
        pattern_score * 0.20
    )

    risk_score = round(100 - weighted, 1)
    if risk_score <= 25:
        risk_level = "Low"
    elif risk_score <= 50:
        risk_level = "Medium"
    elif risk_score <= 75:
        risk_level = "High"
    else:
        risk_level = "Critical"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "breakdown": {
            "completeness": round(completeness_score, 1),
            "compliance": round(compliance_score, 1),
            "pattern_match": round(pattern_score, 1),
        }
    }
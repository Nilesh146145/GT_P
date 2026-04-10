"""
Confidence Scoring Service
Computes the AI Confidence score (0–100%) based on wizard step completion and detail depth.
Step weights reflect their importance — mandatory steps carry higher weight.
"""

from typing import Any, Dict, List


# Step weights (total = 100)
STEP_WEIGHTS = {
    0: 20,   # Mandatory — WHY context, most critical
    1: 18,   # Mandatory — what to build
    2: 15,   # Mandatory — delivery scope
    3: 8,    # Optional — integrations
    4: 7,    # Optional — timeline/team/testing
    5: 12,   # Mandatory — budget & risk
    6: 5,    # Optional — quality standards
    7: 10,   # Mandatory — governance
    8: 5,    # Mandatory — commercial & legal (new)
}

# Confidence penalty for skipping optional steps
SKIP_PENALTIES = {
    3: 8,
    4: 7,
    6: 5,
    9: 3,
}


def score_step_0(data: Dict) -> float:
    """Score Step 0 — Project Context & Discovery (0.0–1.0)"""
    if not data:
        return 0.0
    score = 0.0
    total = 0

    # Section A
    sec_a = data.get("section_a", {})
    if sec_a.get("project_vision") and len(sec_a["project_vision"]) >= 100:
        score += 15
    elif sec_a.get("project_vision"):
        score += 8
    total += 15

    objectives = sec_a.get("business_objectives", [])
    if len(objectives) >= 3:
        score += 15
    elif len(objectives) >= 1:
        score += 8
    total += 15

    pain_points = sec_a.get("pain_points", [])
    if len(pain_points) >= 3:
        score += 10
    elif len(pain_points) >= 1:
        score += 5
    total += 10

    if sec_a.get("strategic_context"):
        score += 5
    total += 5

    if sec_a.get("business_criticality"):
        score += 5
    total += 5

    # Section B
    sec_b = data.get("section_b", {})
    if sec_b.get("desired_future_state") and len(sec_b["desired_future_state"]) >= 100:
        score += 15
    elif sec_b.get("desired_future_state"):
        score += 8
    total += 15

    if sec_b.get("current_state_description") or sec_b.get("current_state_not_applicable"):
        score += 10
    total += 10

    if sec_b.get("previous_attempts"):
        score += 5
    total += 5

    # Section C
    sec_c = data.get("section_c", {})
    profiles = sec_c.get("end_user_profiles", [])
    if len(profiles) >= 2:
        score += 10
    elif len(profiles) >= 1:
        score += 5
    total += 10

    # Section D
    sec_d = data.get("section_d", {})
    metrics = sec_d.get("success_metrics", [])
    if len(metrics) >= 2:
        score += 10
    elif len(metrics) >= 1:
        score += 5
    total += 10

    if sec_d.get("definition_of_success"):
        score += 5
    total += 5

    return round(score / total, 4) if total else 0.0


def score_step_1(data: Dict) -> float:
    if not data:
        return 0.0
    score = 0.0
    total = 0

    sec_a = data.get("section_a", {})
    if sec_a.get("project_title"):
        score += 5
    total += 5
    if sec_a.get("industry"):
        score += 5
    total += 5
    if sec_a.get("project_category"):
        score += 5
    total += 5

    sec_b = data.get("section_b", {})
    modules = sec_b.get("feature_modules", [])
    if len(modules) >= 5:
        score += 30
    elif len(modules) >= 2:
        score += 20
    total += 30

    workflows = sec_b.get("key_workflows", [])
    if len(workflows) >= 2:
        score += 20
    elif len(workflows) >= 1:
        score += 10
    total += 20

    roles = sec_b.get("user_roles", [])
    if len(roles) >= 2:
        score += 15
    elif len(roles) >= 1:
        score += 8
    total += 15

    if sec_b.get("critical_business_rules"):
        score += 10
    total += 10

    sec_c = data.get("section_c", {})
    if sec_c.get("out_of_scope_exclusions"):
        score += 10
    total += 10

    return round(score / total, 4) if total else 0.0


def score_step_2(data: Dict) -> float:
    if not data:
        return 0.0
    score = 0.0
    total = 60

    sec_a = data.get("section_a", {})
    if sec_a.get("deployment"):
        score += 15
    if sec_a.get("go_live"):
        score += 10
    if sec_a.get("ui_ux"):
        score += 10

    sec_b = data.get("section_b", {})
    stack = sec_b.get("technology_stack", "")
    if len(stack) >= 50:
        score += 25
    elif stack:
        score += 15

    return round(score / total, 4) if total else 0.0


def score_step_3(data: Dict) -> float:
    if not data:
        return 0.0
    integrations = data.get("section_a", {}).get("integrations") or []
    if len(integrations) >= 3:
        return 1.0
    elif len(integrations) >= 1:
        return 0.6
    return 0.3  # Skipped but optional — partial credit


def score_step_4(data: Dict) -> float:
    if not data:
        return 0.0
    sec_a = data.get("section_a", {})
    sec_b = data.get("section_b", {})
    sec_c = data.get("section_c", {})

    score = 0.0
    if sec_a.get("start_date") and sec_a.get("target_end_date"):
        score += 0.3
    if sec_b.get("required_roles"):
        score += 0.3
    if sec_c.get("uat"):
        score += 0.4
    return round(min(score, 1.0), 4)


def score_step_5(data: Dict) -> float:
    if not data:
        return 0.0
    sec_a = data.get("section_a", {})
    sec_b = data.get("section_b", {})
    score = 0.0
    if sec_a.get("budget_minimum") and sec_a.get("budget_maximum"):
        score += 0.5
    if sec_b.get("known_risks") and len(sec_b["known_risks"]) >= 1:
        score += 0.3
    if sec_a.get("pricing_model"):
        score += 0.2
    return round(min(score, 1.0), 4)


def score_step_6(data: Dict) -> float:
    if not data:
        return 0.0
    criteria = data.get("project_level_acceptance_criteria", "")
    score = 0.5 if criteria else 0.0
    if data.get("sla_uptime"):
        score += 0.2
    if data.get("browser_compatibility"):
        score += 0.15
    if data.get("device_compatibility"):
        score += 0.15
    return round(min(score, 1.0), 4)


def score_step_7(data: Dict) -> float:
    if not data:
        return 0.0
    score = 0.0
    sec_a = data.get("section_a", {})
    if sec_a.get("non_discrimination_confirmed"):
        score += 0.4
    if sec_a.get("labour_standards"):
        score += 0.1

    sec_c = data.get("section_c", {})
    if sec_c.get("data_sensitivity_level"):
        score += 0.5  # Critical field — no default
    return round(min(score, 1.0), 4)


def score_step_8(data: Dict) -> float:
    if not data:
        return 0.0
    score = 0.0
    sec_a = data.get("section_a", {})
    sec_b = data.get("section_b", {})
    if sec_a.get("ip_ownership"):
        score += 0.35
    if sec_a.get("source_code_repo_ownership"):
        score += 0.15
    if sec_b.get("warranty_period"):
        score += 0.25
    if sec_b.get("change_request_process"):
        score += 0.25
    return round(min(score, 1.0), 4)


STEP_SCORERS = {
    0: score_step_0,
    1: score_step_1,
    2: score_step_2,
    3: score_step_3,
    4: score_step_4,
    5: score_step_5,
    6: score_step_6,
    7: score_step_7,
    8: score_step_8,
}


def compute_confidence(wizard_data: Dict, steps_skipped: List[int]) -> Dict:
    """
    Returns overall confidence score (0–100) and per-step breakdown.
    """
    breakdown = {}
    total_score = 0.0
    total_weight = 0

    for step, weight in STEP_WEIGHTS.items():
        step_data = wizard_data.get(f"step_{step}")
        step_pct = STEP_SCORERS[step](step_data or {})

        # Apply skip penalty for optional steps
        if step in steps_skipped:
            penalty = SKIP_PENALTIES.get(step, 0)
            step_pct = max(0.0, step_pct - (penalty / weight))

        breakdown[f"step_{step}"] = round(step_pct * 100, 1)
        total_score += step_pct * weight
        total_weight += weight

    overall = round((total_score / total_weight) * 100, 1) if total_weight else 0.0
    breakdown["overall"] = overall

    return breakdown


# ──────────────────────────────────────────────
# HALLUCINATION PREVENTION LAYERS
# ──────────────────────────────────────────────

HALLUCINATION_LAYERS = [
    {"layer_id": 1, "name": "Template Selection Validation"},
    {"layer_id": 2, "name": "Scope Boundary Enforcement"},
    {"layer_id": 3, "name": "Clause Library Matching"},
    {"layer_id": 4, "name": "Cross-Step Consistency Check"},
    {"layer_id": 5, "name": "Compliance Alignment"},
    {"layer_id": 6, "name": "Prohibited Clause Detection"},
    {"layer_id": 7, "name": "Business Context Anchoring"},
    {"layer_id": 8, "name": "Evidence Pack Gate Validation"},
]

# Which steps activate which layers
LAYER_ACTIVATION_MAP = {
    1: [1],   # Template selection after Step 1 (platform/category)
    2: [1],   # Scope boundary after Step 1
    3: [7],   # Clause library after Step 7 (data sensitivity)
    4: [2],   # Cross-step consistency after Step 2
    5: [7],   # Compliance alignment after Step 7
    6: [7],   # Prohibited clause after Step 7 (ethical constraints)
    7: [0],   # Business context anchoring after Step 0
    8: [4],   # Evidence pack after Step 4
}


def compute_hallucination_layers(steps_completed: List[int]) -> List[Dict]:
    layers = []
    for layer in HALLUCINATION_LAYERS:
        activation_steps = LAYER_ACTIVATION_MAP.get(layer["layer_id"], [])
        active = all(s in steps_completed for s in activation_steps)
        layers.append({
            **layer,
            "active": active,
            "status": "green" if active else "grey",
        })
    return layers

"""
Test Suite — AI SOW Generator API
Tests all wizard steps, validation rules, confidence scoring, and SOW generation.
Run with: pytest tests/ -v
"""

import pytest
import pytest_asyncio

BASE = "/api/v1"


def _register_json(email: str, password: str = "testpassword123") -> dict:
    """Body for ``POST /auth/register`` (enterprise shape, camelCase)."""
    return {
        "email": email,
        "password": password,
        "firstName": "Test",
        "lastName": "User",
        "orgName": "Test Corp",
        "orgType": "Private Limited",
        "industry": "Technology",
        "companySize": "1-50",
        "adminTitle": "Administrator",
        "acceptTos": True,
        "acceptPp": True,
        "acceptEsa": True,
        "acceptAhp": True,
    }


# ──────────────────────────────────────────────
# FIXTURES (client from tests/conftest.py)
# ──────────────────────────────────────────────

@pytest_asyncio.fixture
async def auth_headers(client):
    """Register + login a test user, return auth headers."""
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@test.com"

    await client.post(f"{BASE}/auth/register", json=_register_json(email))
    res = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def wizard_id(client, auth_headers):
    """Create a wizard and return its ID."""
    res = await client.post(f"{BASE}/wizards", json={"enterprise_id": "ent_001"}, headers=auth_headers)
    assert res.status_code == 201
    return res.json()["wizard_id"]


# ──────────────────────────────────────────────
# SAMPLE STEP DATA
# ──────────────────────────────────────────────

STEP_0_PAYLOAD = {
    "section_a": {
        "project_vision": "A self-service patient portal that allows patients to book, reschedule, and cancel appointments online, reducing clinic administrative workload and improving patient satisfaction scores.",
        "business_objectives": [
            {
                "objective": "Reduce appointment no-show rate",
                "measurable_target": "By 40%",
                "target_timeline": "Within 6 months of go-live"
            },
            {
                "objective": "Reduce admin call volume",
                "measurable_target": "By 30%",
                "target_timeline": "Within 3 months of go-live"
            }
        ],
        "pain_points": [
            {
                "problem_description": "Patients cannot check appointment availability without calling during business hours",
                "who_experiences_it": "Patients"
            },
            {
                "problem_description": "Staff manually enter bookings into a spreadsheet — error-prone and time-consuming",
                "who_experiences_it": "Clinic Admin Staff"
            }
        ],
        "strategic_context": "Customer experience improvement",
        "business_criticality": "Business-Important"
    },
    "section_b": {
        "current_state_not_applicable": False,
        "current_state_description": "Patients currently call a phone number during business hours (9am-5pm) to book appointments. Staff manually enter bookings into a spreadsheet. No automated reminders exist. Average call handling time: 8 minutes per booking.",
        "desired_future_state": "Patients can book, reschedule, and cancel appointments 24/7 through the web portal or mobile app. Automated SMS and email reminders sent 48 hours before appointment. Clinic staff see all bookings in a real-time dashboard.",
        "previous_attempts": "A booking widget was added in 2021 but abandoned — patients found it confusing and clinic staff could not see bookings in real time."
    },
    "section_c": {
        "end_user_profiles": [
            {
                "role_name": "Patients",
                "approximate_user_count": "50,000+",
                "age_range": "36–55",
                "tech_literacy": "Medium",
                "primary_device": "Mobile",
                "geography": "India",
                "accessibility_needs": "Yes"
            },
            {
                "role_name": "Clinic Admin Staff",
                "approximate_user_count": "150",
                "age_range": "18–35",
                "tech_literacy": "High",
                "primary_device": "Desktop",
                "geography": "India",
                "accessibility_needs": "No"
            }
        ],
        "languages": ["English", "Hindi"],
        "translation_provider": "Client provides translated strings",
        "user_expectations": [
            "App must work in low-connectivity rural areas with 2G coverage",
            "Login must not require more than 2 steps for elderly users"
        ]
    },
    "section_d": {
        "success_metrics": [
            {
                "metric_name": "Appointment no-show rate",
                "baseline_value": "22%",
                "target_value": "< 13%",
                "measurement_method": "Clinic booking system monthly report",
                "timeframe": "6 months post go-live"
            }
        ],
        "enterprise_expectations": "We expect weekly progress reports every Friday. We expect all code delivered with inline comments and architecture documentation.",
        "definition_of_success": "Success means the portal is live, patients are actually using it (not just technically delivered), and our admin team is spending less time on the phone within 3 months."
    }
}

STEP_1_PAYLOAD = {
    "section_a": {
        "project_title": "ClinicConnect Patient Portal",
        "client_organisation": "MedCare Hospitals Pvt Ltd",
        "industry": "Healthcare",
        "project_category": "New Build",
        "platform_type": "Full-Stack Platform",
        "client_tech_landscape": "Client runs a legacy appointment system on MS Access. No existing API layer."
    },
    "section_b": {
        "feature_modules": [
            {"module_name": "Patient Authentication", "description": "Email/password + OTP login with mobile-first design and 2-step maximum.", "priority": "Must Have"},
            {"module_name": "Appointment Booking", "description": "Real-time availability calendar, specialist selection, appointment slot booking with instant confirmation.", "priority": "Must Have"},
            {"module_name": "Appointment Management", "description": "View, reschedule, and cancel upcoming appointments. History of past appointments.", "priority": "Must Have"},
            {"module_name": "Automated Reminders", "description": "SMS and email reminders 48h and 24h before appointments. Patient opt-in/opt-out.", "priority": "Must Have"},
            {"module_name": "Admin Dashboard", "description": "Real-time booking view, manual override, patient lookup, daily/weekly reports.", "priority": "Must Have"},
            {"module_name": "Notifications Centre", "description": "In-app notification centre for booking confirmations, changes, reminders.", "priority": "Should Have"}
        ],
        "user_roles": [
            {"role_name": "Patient", "primary_actions": "Register, login, book/reschedule/cancel appointments, view history, manage notifications"},
            {"role_name": "Clinic Admin", "primary_actions": "View all bookings, manually override/create bookings, generate reports, manage doctor schedules"},
            {"role_name": "Super Admin", "primary_actions": "System configuration, user management, analytics, export audit logs"}
        ],
        "key_workflows": [
            {
                "workflow_name": "Patient Appointment Booking",
                "steps": [
                    {"step_number": 1, "description": "Patient logs in or registers"},
                    {"step_number": 2, "description": "Selects specialist / department"},
                    {"step_number": 3, "description": "Views available slots on calendar"},
                    {"step_number": 4, "description": "Selects preferred slot"},
                    {"step_number": 5, "description": "Confirms booking — receives SMS + email confirmation"},
                    {"step_number": 6, "description": "Admin dashboard updates in real time"}
                ],
                "outcome": "Appointment booked, patient and admin both notified, no phone call required"
            }
        ],
        "estimated_screen_count": 22,
        "critical_business_rules": [
            "A patient cannot book more than 3 appointments per specialist per month without admin override",
            "Cancellation must be made at least 2 hours before appointment time",
            "Appointment slots released immediately on cancellation — no hold period"
        ]
    },
    "section_c": {
        "out_of_scope_exclusions": [
            "Video/telemedicine consultation features",
            "Payment gateway integration for appointment fees",
            "EHR/EMR system integration",
            "Prescription management",
            "Insurance billing"
        ],
        "assumptions": [
            "Client will provide doctor schedule data in CSV format within 5 business days of kick-off",
            "Client will provide SMS gateway API credentials (Twilio/MSG91) within 5 business days",
            "UAT environment will be provided by GlimmoraTeam on AWS"
        ],
        "constraints": [
            "Must support offline booking queue for 2G connectivity patients",
            "Must comply with DPDP Act (India) for patient data handling"
        ],
        "data_migration": {
            "in_scope": False
        }
    }
}

STEP_2_PAYLOAD = {
    "section_a": {
        "development_scope": {
            "frontend": True,
            "backend": True,
            "api": True,
            "database_design": True,
            "third_party_integration": True,
            "ci_cd_setup": True
        },
        "ui_ux": {
            "scope": "In scope",
            "wireframes": True,
            "high_fidelity_mockups": True,
            "design_system": True,
            "clickable_prototype": False,
            "brand_identity": False
        },
        "deployment": {
            "scope": "Deploy to cloud",
            "cloud": {
                "provider": "AWS",
                "containerisation_k8s": True,
                "environments": ["Dev", "Staging", "Production"],
                "aws_services": {
                    "ec2_ecs_eks": True,
                    "rds_aurora": True,
                    "s3": True,
                    "cloudfront": True,
                    "lambda_": False,
                    "api_gateway": True,
                    "load_balancer": True
                }
            }
        },
        "go_live": {
            "scope": "Go-live + post-go-live hypercare",
            "hypercare_duration": "2 weeks",
            "hypercare_support_level": "Bug fixes only"
        }
    },
    "section_b": {
        "technology_stack": "React 18 + TypeScript frontend, React Native (Expo) mobile, Node.js 20 / NestJS backend, PostgreSQL 15 + Redis 7, Docker + AWS ECS, AWS RDS Aurora, S3, CloudFront, API Gateway, Jest + Playwright testing.",
        "scalability_performance": {
            "concurrent_users_target": 5000,
            "response_time_sla_ms": 500,
            "expected_data_volume": "Medium 1–100GB"
        }
    }
}

STEP_5_PAYLOAD = {
    "section_a": {
        "budget_minimum": 2500000,
        "budget_maximum": 3500000,
        "currency": "INR",
        "pricing_model": "Fixed Price",
        "budget_breakdown_preference": "Milestone-based"
    },
    "section_b": {
        "known_risks": [
            {
                "description": "Third-party SMS gateway rate limits may restrict throughput at peak load",
                "likelihood": "Medium",
                "impact": "High"
            },
            {
                "description": "Client doctor schedule data may be incomplete or inconsistently formatted",
                "likelihood": "High",
                "impact": "Medium"
            },
            {
                "description": "2G offline sync complexity may extend development timeline",
                "likelihood": "Medium",
                "impact": "Medium"
            }
        ],
        "project_constraints": "Must complete development within 6 months due to hospital board commitment to patients.",
        "contingency_budget": "10%",
        "escalation_process": "Joint committee"
    }
}

STEP_7_PAYLOAD = {
    "section_a": {
        "non_discrimination_confirmed": True,
        "labour_standards": "ILO Core Labour Standards (international)",
        "accessibility_requirements": "WCAG 2.1 Level AA",
        "prohibited_work_categories": ["No dark pattern UX", "No child-directed data collection"]
    },
    "section_b": {
        "personal_data_involved": True,
        "personal_data_detail": {
            "data_categories": ["Name & contact details", "Health records", "Location data"],
            "applicable_privacy_laws": ["GDPR (EU)", "DPDP Act (India)"],
            "dpa_required": "Yes"
        },
        "privacy_impact_assessment": "In progress"
    },
    "section_c": {
        "data_sensitivity_level": "Confidential",
        "encryption_requirements": "Both",
        "regulatory_frameworks": ["DPDP Act (India)", "ISO 27001"],
        "data_residency": "India only",
        "access_control_model": "RBAC"
    }
}

STEP_8_PAYLOAD = {
    "section_a": {
        "ip_ownership": "Client owns all IP and source code",
        "source_code_repo_ownership": "GlimmoraTeam hosts during delivery, transfers to client on M3 payment",
        "portfolio_reference_rights": "GlimmoraTeam may reference this project without disclosing client name",
        "oss_policy": "Client accepts OSS components with compatible licences (MIT, Apache, BSD)"
    },
    "section_b": {
        "third_party_licensing": "Client pays all third-party service and licence costs directly",
        "warranty_period": "90 days",
        "change_request_process": {
            "model": "All changes formally priced and approved before work begins",
            "approver_name": "Priya Sharma",
            "approver_role": "Head of Digital Transformation"
        }
    }
}


# ══════════════════════════════════════════════
# AUTH TESTS
# ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_register_and_login(client):
    import uuid
    email = f"newuser_{uuid.uuid4().hex[:6]}@test.com"
    res = await client.post(
        f"{BASE}/auth/register",
        json=_register_json(email, password="securepass123")
        | {"firstName": "Jane", "lastName": "Doe", "orgName": "ACME Corp"},
    )
    assert res.status_code == 201
    assert res.json()["success"] is True

    res2 = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "securepass123"},
    )
    assert res2.status_code == 200
    assert "access_token" in res2.json()


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client, auth_headers):
    # Get the current user's email from /me
    me = await client.get(f"{BASE}/auth/me", headers=auth_headers)
    email = me.json()["data"]["email"]
    res = await client.post(
        f"{BASE}/auth/register",
        json=_register_json(email, password="duppassword12")
        | {"firstName": "Dup", "lastName": "User", "orgName": "X"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_wrong_password(client, auth_headers):
    me = await client.get(f"{BASE}/auth/me", headers=auth_headers)
    email = me.json()["data"]["email"]
    res = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "wrongpass"},
    )
    assert res.status_code == 401


# ══════════════════════════════════════════════
# WIZARD CREATION TESTS
# ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_wizard(client, auth_headers):
    res = await client.post(f"{BASE}/wizards", json={"enterprise_id": "ent_test"}, headers=auth_headers)
    assert res.status_code == 201
    data = res.json()
    assert "wizard_id" in data
    assert len(data["wizard_id"]) > 0


@pytest.mark.asyncio
async def test_get_wizard(client, auth_headers, wizard_id):
    res = await client.get(f"{BASE}/wizards/{wizard_id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["id"] == wizard_id
    assert data["status"] == "draft"
    assert data["steps_completed"] == []


@pytest.mark.asyncio
async def test_list_wizards(client, auth_headers, wizard_id):
    res = await client.get(f"{BASE}/wizards", headers=auth_headers)
    assert res.status_code == 200
    wizards = res.json()["data"]
    assert any(w["id"] == wizard_id for w in wizards)


# ══════════════════════════════════════════════
# STEP 0 TESTS — Most critical step
# ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_step_0_success(client, auth_headers, wizard_id):
    res = await client.put(
        f"{BASE}/wizards/{wizard_id}/steps/0",
        json=STEP_0_PAYLOAD,
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["step"] == 0
    assert 0 in data["steps_completed"]
    assert data["confidence_score"] > 0


@pytest.mark.asyncio
async def test_step_0_confidence_increases_with_detail(client, auth_headers, wizard_id):
    # Minimal payload
    minimal = {
        "section_a": {
            "project_vision": "A" * 50,
            "business_objectives": [{"objective": "Obj", "measurable_target": "10%", "target_timeline": "6 months"}],
            "pain_points": [{"problem_description": "Problem X", "who_experiences_it": "Users"}],
            "business_criticality": "Standard"
        },
        "section_b": {"current_state_not_applicable": True, "desired_future_state": "B" * 30},
        "section_c": {"end_user_profiles": [{"role_name": "User", "approximate_user_count": "100", "age_range": "18–35", "tech_literacy": "Medium", "primary_device": "Desktop", "geography": "India", "accessibility_needs": "No"}]},
        "section_d": {"success_metrics": [{"metric_name": "Metric", "baseline_value": "0", "target_value": "10", "measurement_method": "Report", "timeframe": "6 months"}], "definition_of_success": "C" * 30}
    }
    res_min = await client.put(f"{BASE}/wizards/{wizard_id}/steps/0", json=minimal, headers=auth_headers)
    score_min = res_min.json()["confidence_score"]

    res_full = await client.put(f"{BASE}/wizards/{wizard_id}/steps/0", json=STEP_0_PAYLOAD, headers=auth_headers)
    score_full = res_full.json()["confidence_score"]

    assert score_full >= score_min, "More detailed step 0 should yield higher confidence"


@pytest.mark.asyncio
async def test_step_0_vision_too_short(client, auth_headers, wizard_id):
    payload = dict(STEP_0_PAYLOAD)
    payload["section_a"] = dict(STEP_0_PAYLOAD["section_a"])
    payload["section_a"]["project_vision"] = "Short"  # < 50 chars
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/0", json=payload, headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_step_0_requires_at_least_one_objective(client, auth_headers, wizard_id):
    payload = dict(STEP_0_PAYLOAD)
    payload["section_a"] = dict(STEP_0_PAYLOAD["section_a"])
    payload["section_a"]["business_objectives"] = []
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/0", json=payload, headers=auth_headers)
    assert res.status_code == 422


# ══════════════════════════════════════════════
# STEP 1 TESTS
# ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_step_1_success(client, auth_headers, wizard_id):
    await client.put(f"{BASE}/wizards/{wizard_id}/steps/0", json=STEP_0_PAYLOAD, headers=auth_headers)
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/1", json=STEP_1_PAYLOAD, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert 1 in data["steps_completed"]


@pytest.mark.asyncio
async def test_step_1_requires_min_2_modules(client, auth_headers, wizard_id):
    payload = dict(STEP_1_PAYLOAD)
    payload["section_b"] = dict(STEP_1_PAYLOAD["section_b"])
    payload["section_b"]["feature_modules"] = [STEP_1_PAYLOAD["section_b"]["feature_modules"][0]]  # Only 1
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/1", json=payload, headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_step_1_requires_exclusions(client, auth_headers, wizard_id):
    payload = dict(STEP_1_PAYLOAD)
    payload["section_c"] = dict(STEP_1_PAYLOAD["section_c"])
    payload["section_c"]["out_of_scope_exclusions"] = []
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/1", json=payload, headers=auth_headers)
    assert res.status_code == 422


# ══════════════════════════════════════════════
# STEP 2 TESTS
# ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_step_2_success(client, auth_headers, wizard_id):
    await client.put(f"{BASE}/wizards/{wizard_id}/steps/0", json=STEP_0_PAYLOAD, headers=auth_headers)
    await client.put(f"{BASE}/wizards/{wizard_id}/steps/1", json=STEP_1_PAYLOAD, headers=auth_headers)
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/2", json=STEP_2_PAYLOAD, headers=auth_headers)
    assert res.status_code == 200
    assert 2 in res.json()["steps_completed"]


@pytest.mark.asyncio
async def test_step_2_requires_at_least_one_dev_scope(client, auth_headers, wizard_id):
    payload = dict(STEP_2_PAYLOAD)
    payload["section_a"] = dict(STEP_2_PAYLOAD["section_a"])
    payload["section_a"]["development_scope"] = {
        "frontend": False, "backend": False, "api": False,
        "database_design": False, "third_party_integration": False, "ci_cd_setup": False
    }
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/2", json=payload, headers=auth_headers)
    assert res.status_code == 422


# ══════════════════════════════════════════════
# SKIP TESTS
# ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_skip_optional_step_3(client, auth_headers, wizard_id):
    res = await client.post(f"{BASE}/wizards/{wizard_id}/steps/3/skip", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["skipped"] is True
    assert data["confidence_penalty"] == 8.0
    assert 3 in data.get("steps_skipped", []) or "step" in data


@pytest.mark.asyncio
async def test_cannot_skip_mandatory_step(client, auth_headers, wizard_id):
    # Step 0 is mandatory — no skip endpoint. Try a fake call
    res = await client.post(f"{BASE}/wizards/{wizard_id}/steps/0/skip", headers=auth_headers)
    assert res.status_code == 404  # No such route exists for mandatory steps


# ══════════════════════════════════════════════
# STEP 7 TESTS — Governance hard blocks
# ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_step_7_non_discrimination_required(client, auth_headers, wizard_id):
    payload = dict(STEP_7_PAYLOAD)
    payload["section_a"] = dict(STEP_7_PAYLOAD["section_a"])
    payload["section_a"]["non_discrimination_confirmed"] = False
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/7", json=payload, headers=auth_headers)
    assert res.status_code == 422
    body = res.json()
    assert any("non-discrimination" in str(e).lower() or "mandatory" in str(e).lower()
               for e in body.get("errors", []))


@pytest.mark.asyncio
async def test_step_7_personal_data_requires_privacy_law(client, auth_headers, wizard_id):
    payload = dict(STEP_7_PAYLOAD)
    payload["section_b"] = {"personal_data_involved": True}  # Missing detail
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/7", json=payload, headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_step_7_save_success(client, auth_headers, wizard_id):
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/7", json=STEP_7_PAYLOAD, headers=auth_headers)
    assert res.status_code == 200
    assert 7 in res.json()["steps_completed"]


# ══════════════════════════════════════════════
# STEP 5 TESTS — Budget validation
# ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_budget_max_less_than_min_rejected(client, auth_headers, wizard_id):
    payload = dict(STEP_5_PAYLOAD)
    payload["section_a"] = dict(STEP_5_PAYLOAD["section_a"])
    payload["section_a"]["budget_minimum"] = 5000000
    payload["section_a"]["budget_maximum"] = 1000000  # Less than min
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/5", json=payload, headers=auth_headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_step_5_save_success(client, auth_headers, wizard_id):
    res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/5", json=STEP_5_PAYLOAD, headers=auth_headers)
    assert res.status_code == 200
    assert 5 in res.json()["steps_completed"]


# ══════════════════════════════════════════════
# FSD FLOW — WIZ-008 / Step 9 reminders
# ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_wiz008_migration_in_scope_requires_step2_section_c(client, auth_headers, wizard_id):
    """When Step 1 marks data migration in scope, Step 2 must include Section C technical detail."""
    import copy

    assert await client.put(
        f"{BASE}/wizards/{wizard_id}/steps/0", json=STEP_0_PAYLOAD, headers=auth_headers
    ).status_code == 200
    p1 = copy.deepcopy(STEP_1_PAYLOAD)
    p1["section_c"] = copy.deepcopy(p1["section_c"])
    p1["section_c"]["data_migration"] = {**p1["section_c"]["data_migration"], "in_scope": True}
    assert await client.put(
        f"{BASE}/wizards/{wizard_id}/steps/1", json=p1, headers=auth_headers
    ).status_code == 200
    res2 = await client.put(
        f"{BASE}/wizards/{wizard_id}/steps/2", json=STEP_2_PAYLOAD, headers=auth_headers
    )
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_step_9_summary_flow_reminders_when_wizard_ready(client, auth_headers, wizard_id):
    await _complete_all_mandatory_steps(client, auth_headers, wizard_id)
    summary = await client.get(f"{BASE}/wizards/{wizard_id}/steps/9/summary", headers=auth_headers)
    assert summary.status_code == 200
    data = summary.json()["data"]
    assert data["can_generate"] is True
    assert "flow_reminders" in data
    assert len(data["flow_reminders"]) >= 1


# ══════════════════════════════════════════════
# GENERATION TESTS
# ══════════════════════════════════════════════

async def _complete_all_mandatory_steps(client, auth_headers, wizard_id):
    """Helper: fills all 6 mandatory steps."""
    for step, payload in [
        (0, STEP_0_PAYLOAD),
        (1, STEP_1_PAYLOAD),
        (2, STEP_2_PAYLOAD),
        (5, STEP_5_PAYLOAD),
        (7, STEP_7_PAYLOAD),
        (8, STEP_8_PAYLOAD),
    ]:
        res = await client.put(f"{BASE}/wizards/{wizard_id}/steps/{step}", json=payload, headers=auth_headers)
        assert res.status_code == 200, f"Step {step} failed: {res.text}"


@pytest.mark.asyncio
async def test_generate_fails_without_mandatory_steps(client, auth_headers, wizard_id):
    res = await client.post(
        f"{BASE}/wizards/{wizard_id}/generate",
        json={"business_owner_approver_id": "user_001", "final_approver_id": "user_002"},
        headers=auth_headers
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_step_9_summary_shows_blocking_errors(client, auth_headers, wizard_id):
    res = await client.get(f"{BASE}/wizards/{wizard_id}/steps/9/summary", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["can_generate"] is False
    assert len(data["blocking_errors"]) > 0


@pytest.mark.asyncio
async def test_full_generate_flow(client, auth_headers, wizard_id):
    """Full happy-path: complete all mandatory steps → generate SOW → verify quality metrics."""
    await _complete_all_mandatory_steps(client, auth_headers, wizard_id)

    # Check Step 9 summary shows ready
    summary = await client.get(f"{BASE}/wizards/{wizard_id}/steps/9/summary", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["data"]["can_generate"] is True

    # Generate
    res = await client.post(
        f"{BASE}/wizards/{wizard_id}/generate",
        json={"business_owner_approver_id": "user_bo_001", "final_approver_id": "user_fa_001"},
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert "sow_id" in data
    assert data["quality_metrics"]["overall_confidence"] > 0

    # Get generated SOW
    sow_id = data["sow_id"]
    sow_res = await client.get(f"{BASE}/sows/{sow_id}", headers=auth_headers)
    assert sow_res.status_code == 200
    sow = sow_res.json()["data"]
    assert sow["status"] == "draft"
    assert sow["generated_content"] is not None

    # Hallucination analysis
    ha_res = await client.get(f"{BASE}/sows/{sow_id}/hallucination-analysis", headers=auth_headers)
    assert ha_res.status_code == 200
    ha = ha_res.json()["data"]
    assert "layers" in ha
    assert ha["layers_active"] > 0

    return sow_id


@pytest.mark.asyncio
async def test_sow_submit_action(client, auth_headers, wizard_id):
    sow_id = await test_full_generate_flow(client, auth_headers, wizard_id)

    # Check if can submit (depends on hallucination layers)
    ha_res = await client.get(f"{BASE}/sows/{sow_id}/hallucination-analysis", headers=auth_headers)
    can_submit = ha_res.json()["data"]["can_submit"]

    if can_submit:
        res = await client.post(
            f"{BASE}/sows/{sow_id}/action",
            json={"action": "submit"},
            headers=auth_headers
        )
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "in_review"


@pytest.mark.asyncio
async def test_sow_reject_regenerate(client, auth_headers, wizard_id):
    sow_id = await test_full_generate_flow(client, auth_headers, wizard_id)
    res = await client.post(
        f"{BASE}/sows/{sow_id}/action",
        json={"action": "reject_regenerate", "change_notes": "Need to revise scope."},
        headers=auth_headers
    )
    assert res.status_code == 200
    wiz = await client.get(f"{BASE}/wizards/{wizard_id}", headers=auth_headers)
    assert wiz.status_code == 200
    wdata = wiz.json()["data"]
    assert wdata.get("sow_id") in (None, "")
    assert wdata["status"] == "completed"
    gone = await client.get(f"{BASE}/sows/{sow_id}", headers=auth_headers)
    assert gone.status_code == 404


# ══════════════════════════════════════════════
# CONFIDENCE SCORING UNIT TESTS
# ══════════════════════════════════════════════

def test_confidence_scorer_step0():
    from app.services.confidence import score_step_0
    full = score_step_0(STEP_0_PAYLOAD)
    assert full > 0.7, f"Full step 0 should score > 70%, got {full}"


def test_confidence_scorer_empty():
    from app.services.confidence import score_step_0
    empty = score_step_0({})
    assert empty == 0.0


def test_confidence_compute_overall():
    from app.services.confidence import compute_confidence
    wizard_data = {
        "step_0": STEP_0_PAYLOAD,
        "step_1": STEP_1_PAYLOAD,
        "step_2": STEP_2_PAYLOAD,
        "step_3": None,
        "step_4": None,
        "step_5": STEP_5_PAYLOAD,
        "step_6": None,
        "step_7": STEP_7_PAYLOAD,
        "step_8": STEP_8_PAYLOAD,
    }
    result = compute_confidence(wizard_data, steps_skipped=[3, 4, 6])
    assert result["overall"] > 60, f"Overall confidence should be > 60%, got {result['overall']}"
    assert "step_0" in result
    assert "step_7" in result


def test_hallucination_layers_activate_with_steps():
    from app.services.confidence import compute_hallucination_layers
    layers_none = compute_hallucination_layers([])
    assert all(not l["active"] for l in layers_none)

    layers_with_0_and_1 = compute_hallucination_layers([0, 1])
    active = [l for l in layers_with_0_and_1 if l["active"]]
    assert len(active) >= 3  # Layer 1 (step 1), Layer 2 (step 1), Layer 7 (step 0)

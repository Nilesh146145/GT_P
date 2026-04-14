"""Tests for Manual SOW intake API (/api/v1/sow)."""

import asyncio
import io
import socket

import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from app.core.database import close_db, connect_db
from app.core.security import get_current_user
from app.main import app
from app.schemas.manual_sow.manual_sow_platform_type import ManualSowPlatformType

BASE = "/api/v1"


def test_stored_ai_stale_when_summary_platform_mismatches_delivery():
    from app.services.manual_sow.manual_sow_service import _stored_ai_tech_stack_stale_for_delivery

    ai = {
        "title": "Full-stack baseline",
        "summary": "Suitable for an SOW (platform type FULL_STACK).",
        "AI-generated-tech-stack": ["x"] * 8,
    }
    doc = {}
    cd = {
        "deliveryScope": {
            "platformType": "MOBILE_HYBRID",
            "developmentScope": ["Frontend", "Backend"],
            "uiuxDesignScope": "in_scope",
            "deploymentScope": "cloud",
            "goLiveScope": "go_live",
            "dataMigrationScope": "not_in_scope",
        }
    }
    assert _stored_ai_tech_stack_stale_for_delivery(doc, ai, cd) is True

    doc2 = {"ai_tech_stack_scope_fp": {"pt": "MOBILE_HYBRID", "dev": ["backend", "frontend"]}}
    assert _stored_ai_tech_stack_stale_for_delivery(doc2, ai, cd) is False


def test_strip_delivery_fields_from_business_context():
    from app.services.manual_sow.commercial_validation import strip_delivery_scope_fields_from_business_context

    messy = {
        "projectVision": "x" * 50,
        "businessCriticality": "standard",
        "currentState": "a",
        "desiredFutureState": "b",
        "definitionOfSuccess": "c",
        "platformType": "Mobile-Hybrid ",
        "developmentScope": ["Frontend"],
        "uiuxDesignScope": "in_scope",
        "deploymentScope": "cloud",
        "goLiveScope": "go_live",
        "dataMigrationScope": "not_in_scope",
    }
    clean, stripped = strip_delivery_scope_fields_from_business_context(messy)
    assert stripped is True
    assert "platformType" not in clean
    assert "developmentScope" not in clean
    assert clean["projectVision"] == messy["projectVision"]


def test_normalize_platform_type_accepts_human_labels():
    from app.schemas.manual_sow.manual_sow_platform_type import normalize_manual_sow_platform_type

    assert normalize_manual_sow_platform_type("web application") == "WEB_APPLICATION"
    assert normalize_manual_sow_platform_type("Web Application") == "WEB_APPLICATION"
    assert normalize_manual_sow_platform_type("WEB_APPLICATION") == "WEB_APPLICATION"
    assert normalize_manual_sow_platform_type("mobile hybrid") == "MOBILE_HYBRID"


def test_normalize_platform_type_common_aliases():
    from app.schemas.manual_sow.manual_sow_platform_type import normalize_manual_sow_platform_type

    assert normalize_manual_sow_platform_type("backend only") == "API_BACKEND_ONLY"
    assert normalize_manual_sow_platform_type("PWA") == "WEB_APPLICATION"
    assert normalize_manual_sow_platform_type("react native") == "MOBILE_HYBRID"
    assert normalize_manual_sow_platform_type("data platform") == "DATA_PLATFORM"
    assert normalize_manual_sow_platform_type("desktop app") == "DESKTOP"


@pytest.mark.parametrize("member", list(ManualSowPlatformType))
def test_each_platform_type_validates_catalog_and_mock_payload(member):
    from app.schemas.manual_sow.enums import CommercialSectionKey
    from app.services.manual_sow.ai_tech_stack_service import (
        build_mock_ai_tech_stack_payload,
        sow_technology_catalog_for_delivery_scope,
    )
    from app.services.manual_sow.commercial_validation import validate_section
    from app.services.manual_sow.manual_sow_service import MIN_STORED_AI_TECH_STACK_ITEMS

    base_ds = {
        "platformType": member.value,
        "developmentScope": ["Backend", "Integration"],
        "uiuxDesignScope": "in_scope",
        "deploymentScope": "cloud",
        "goLiveScope": "go_live",
        "dataMigrationScope": "not_in_scope",
    }
    ok, err = validate_section(CommercialSectionKey.deliveryScope, base_ds)
    assert ok, (member.value, err)

    human_pt = member.value.replace("_", " ").lower()
    ok_h, err_h = validate_section(CommercialSectionKey.deliveryScope, {**base_ds, "platformType": human_pt})
    assert ok_h, (member.value, human_pt, err_h)

    cd = {"deliveryScope": base_ds, "businessContext": {}, "techIntegrations": {}}
    cat = sow_technology_catalog_for_delivery_scope(cd)
    assert len(cat) >= 8, member.value

    payload = build_mock_ai_tech_stack_payload(project_title="P", client_org="C", commercial_details=cd)
    stack = payload.get("AI-generated-tech-stack") or []
    assert len(stack) >= MIN_STORED_AI_TECH_STACK_ITEMS, member.value
    assert member.value in str(payload.get("summary") or "")
    line = str(payload.get("technologyStackLine") or "")
    assert " · " in line and "(" in line, member.value
    assert payload.get("scalabilityPerformance")
    assert payload.get("userManagementScope")
    assert payload.get("ssoRequired") is not None


def test_delivery_scope_fingerprint_normalizes_human_platform_type():
    from app.services.manual_sow.manual_sow_service import _delivery_scope_ai_fingerprint

    a = {"platformType": "WEB_APPLICATION", "developmentScope": ["Backend"]}
    b = {"platformType": "web application", "developmentScope": ["Backend"]}
    assert _delivery_scope_ai_fingerprint(a) == _delivery_scope_ai_fingerprint(b)


def test_stored_ai_conflict_when_web_scope_but_mobile_stack():
    from app.services.manual_sow.ai_tech_stack_service import stored_ai_tech_stack_conflicts_with_delivery_scope

    cd = {
        "deliveryScope": {"platformType": "WEB_APPLICATION", "developmentScope": ["Frontend", "Backend"]},
        "techIntegrations": {},
    }
    ai = {
        "title": "x",
        "tags": ["Flutter", "Python"],
        "AI-generated-tech-stack": ["Flutter", "Python", "PostgreSQL", "Redis", "REST", "Git", "OpenAPI", "JWT"],
        "technologyStackLine": "Flutter (frontend) · Python (API layer)",
        "scalabilityPerformance": "a" * 50,
        "userManagementScope": "b" * 30,
        "ssoRequired": True,
        "summary": "c" * 20,
    }
    assert stored_ai_tech_stack_conflicts_with_delivery_scope(cd, ai) is True
    assert stored_ai_tech_stack_conflicts_with_delivery_scope(
        {**cd, "deliveryScope": {**cd["deliveryScope"], "platformType": "MOBILE_HYBRID"}},
        ai,
    ) is False
    assert stored_ai_tech_stack_conflicts_with_delivery_scope(
        cd,
        {
            **ai,
            "tags": ["React", "TypeScript"],
            "AI-generated-tech-stack": [
                "React",
                "TypeScript",
                "Python",
                "PostgreSQL",
                "Redis",
                "REST",
                "Git",
                "OpenAPI",
            ],
            "technologyStackLine": "React (frontend) · Python (API layer)",
        },
    ) is False


def test_web_mock_drops_mobile_tokens_from_stale_technology_stack_text():
    """Regex extraction from legacy ``technologyStack`` must not override WEB_APPLICATION with mobile stacks."""
    from app.services.manual_sow.ai_tech_stack_service import build_mock_ai_tech_stack_payload

    ds = {
        "platformType": "WEB_APPLICATION",
        "developmentScope": ["Frontend", "Backend"],
        "uiuxDesignScope": "in_scope",
        "deploymentScope": "cloud",
        "goLiveScope": "go_live",
        "dataMigrationScope": "not_in_scope",
    }
    cd = {
        "deliveryScope": ds,
        "businessContext": {},
        "techIntegrations": {
            "technologyStack": "Food delivery mobile app using Flutter Kotlin Swift Firebase on iOS and Android.",
        },
    }
    payload = build_mock_ai_tech_stack_payload(project_title="Food Delivery", client_org="Acme", commercial_details=cd)
    stack = payload.get("AI-generated-tech-stack") or []
    lowered = {str(x).strip().lower() for x in stack}
    assert "flutter" not in lowered
    assert "kotlin" not in lowered
    assert "swift" not in lowered
    assert any(x in lowered for x in ("react", "typescript", "vite"))


def test_merge_delivery_scope_does_not_revert_web_label_to_mobile_seed():
    """Invalid enum strings used to fail validation so repair replaced platformType with extraction seed."""
    from app.services.manual_sow.commercial_prefill import merge_delivery_scope_with_repair

    common = {
        "developmentScope": ["Frontend"],
        "uiuxDesignScope": "in_scope",
        "deploymentScope": "cloud",
        "goLiveScope": "go_live",
        "dataMigrationScope": "not_in_scope",
    }
    existing = {**common, "platformType": "web application"}
    seed = {**common, "platformType": "MOBILE_HYBRID"}
    merged = merge_delivery_scope_with_repair(seed, existing)
    assert merged["platformType"] == "WEB_APPLICATION"


def test_delivery_scope_requires_platform_type():
    from app.schemas.manual_sow.enums import CommercialSectionKey
    from app.services.manual_sow.commercial_validation import validate_section

    ds = {
        "developmentScope": ["Backend"],
        "uiuxDesignScope": "in_scope",
        "deploymentScope": "cloud",
        "goLiveScope": "go_live",
        "dataMigrationScope": "not_in_scope",
    }
    ok, err = validate_section(CommercialSectionKey.deliveryScope, ds)
    assert not ok
    assert "platformType" in err


def test_ai_tech_stack_generation_ready_requires_ab_complete():
    from app.schemas.manual_sow.enums import CommercialSectionKey, CommercialSectionStatus
    from app.services.manual_sow.commercial_validation import ai_tech_stack_generation_ready

    cd = {
        "businessContext": {
            "projectVision": "x" * 50,
            "businessCriticality": "standard",
            "currentState": "a",
            "desiredFutureState": "b",
            "definitionOfSuccess": "c",
        },
        "deliveryScope": {
            "platformType": "WEB_APPLICATION",
            "developmentScope": ["Frontend"],
            "uiuxDesignScope": "in_scope",
            "deploymentScope": "cloud",
            "goLiveScope": "go_live",
            "dataMigrationScope": "not_in_scope",
        },
    }
    ss_incomplete = {
        CommercialSectionKey.businessContext.value: CommercialSectionStatus.in_progress.value,
        CommercialSectionKey.deliveryScope.value: CommercialSectionStatus.complete.value,
    }
    ready, hints = ai_tech_stack_generation_ready(ss_incomplete, cd)
    assert ready is False
    assert "businessContext" in hints

    ss_ok = {
        CommercialSectionKey.businessContext.value: CommercialSectionStatus.complete.value,
        CommercialSectionKey.deliveryScope.value: CommercialSectionStatus.complete.value,
    }
    assert ai_tech_stack_generation_ready(ss_ok, cd)[0] is True


def test_stored_ai_tech_stack_complete_requires_minimum_items():
    from app.services.manual_sow.manual_sow_service import (
        MIN_STORED_AI_TECH_STACK_ITEMS,
        _stored_ai_tech_stack_complete,
    )

    thin = {
        "title": "Technology outline",
        "tags": ["Docker", "AWS"],
        "AI-generated-tech-stack": ["Docker", "AWS"],
        "summary": "Mock / offline suggestion with enough length.",
    }
    assert _stored_ai_tech_stack_complete(thin) is False

    full_stack = ["T" + str(i) for i in range(MIN_STORED_AI_TECH_STACK_ITEMS)]
    ok = {
        "title": "Full baseline",
        "tags": full_stack[:3],
        "AI-generated-tech-stack": full_stack,
        "technologyStackLine": "T0 (frontend) · T1 (API layer) · T2 (database)",
        "scalabilityPerformance": "Autoscale APIs; cache reads; load test before UAT.",
        "userManagementScope": "RBAC and corporate IdP when SSO is required.",
        "ssoRequired": True,
        "summary": "Professional SOW-style summary text here.",
    }
    assert _stored_ai_tech_stack_complete(ok) is True


def test_stored_ai_not_complete_when_legacy_long_tech_list():
    from app.services.manual_sow.manual_sow_service import _stored_ai_tech_stack_complete

    legacy = {
        "title": "Cross-platform mobile technology baseline",
        "tags": ["Flutter"] * 12,
        "AI-generated-tech-stack": ["Flutter", "Dart", "Firebase", "REST", "JSON", "Git", "GitHub Actions", "Fastlane", "Google Play", "App Store Connect", "Docker", "AWS", "Python", "FastAPI", "Pydantic", "Uvicorn", "SQLAlchemy", "Alembic", "PostgreSQL", "Redis", "OpenAPI", "JWT", "OAuth 2.0", "Amazon RDS", "Terraform", "Prometheus", "Grafana", "RabbitMQ", "Celery", "Webhooks", "Kafka"],
        "summary": "Old verbose mock shape with many duplicate infrastructure tools listed.",
    }
    assert _stored_ai_tech_stack_complete(legacy) is False


def test_technology_stack_from_ai_payload_derives_string():
    from app.services.manual_sow.manual_sow_service import ManualSowService

    long_summary = "A" * 12
    assert ManualSowService._technology_stack_from_ai_payload(
        {"summary": long_summary, "AI-generated-tech-stack": ["Python"]}
    ) == long_summary
    assert (
        ManualSowService._technology_stack_from_ai_payload(
            {"summary": "tiny", "AI-generated-tech-stack": ["Python", "FastAPI", "PostgreSQL"]}
        )
        == "Python, FastAPI, PostgreSQL"
    )
    assert ManualSowService._technology_stack_from_ai_payload({}) is None


def _mongo_listening(host: str = "127.0.0.1", port: int = 27017, timeout: float = 0.4) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


@pytest_asyncio.fixture
async def client_auth():
    """Bypass JWT + MFA; requires MongoDB for persistence."""
    if not _mongo_listening():
        pytest.skip("MongoDB not reachable on localhost:27017")
    await connect_db()
    uid = str(ObjectId())

    async def _fake_user():
        return {
            "id": uid,
            "email": "manual_sow_tester@test.com",
            "full_name": "Manual SOW Tester",
            "role": "contributor",
            "mfa_enabled": False,
        }

    app.dependency_overrides[get_current_user] = _fake_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c, uid
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        await close_db()


def _minimal_pdf_bytes() -> bytes:
    """Tiny valid PDF for upload tests."""
    return b"""%PDF-1.4
1 0 obj<<>>endobj
2 0 obj<</Length 44>>stream
BT /F1 12 Tf 100 700 Td (Hello) Tj ET
endstream
endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Contents 2 0 R>>endobj
xref
0 4
trailer<</Size 4/Root 1 0 R>>
startxref
100
%%EOF"""


@pytest.mark.asyncio
async def test_upload_and_list(client_auth):
    client, _uid = client_auth
    files = {"file": ("test.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")}
    data = {"projectTitle": "My Project Title", "clientOrganisation": "ACME Corp"}
    res = await client.post(f"{BASE}/sow/upload", files=files, data=data)
    if res.status_code != 200:
        pytest.skip(f"MongoDB or storage required: {res.status_code} {res.text}")
    body = res.json()
    assert "sow_id" in body
    assert body["status"] == "parsing"

    r2 = await client.get(f"{BASE}/sow")
    assert r2.status_code == 200
    lst = r2.json()
    assert "sows" in lst
    assert "pagination" in lst


@pytest.mark.asyncio
async def test_commercial_validate_endpoint(client_auth):
    """PATCH commercial + validate without full workflow."""
    client, _uid = client_auth
    files = {"file": ("x.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")}
    data = {"projectTitle": "Title Here Long Enough", "clientOrganisation": "ACME"}
    up = await client.post(f"{BASE}/sow/upload", files=files, data=data)
    if up.status_code != 200:
        pytest.skip(f"MongoDB or storage required: {up.status_code}")
    sow_id = up.json()["sow_id"]

    payload = {
        "projectVision": "x" * 50,
        "businessCriticality": "standard",
        "currentState": "a",
        "desiredFutureState": "b",
        "definitionOfSuccess": "c",
    }
    v = await client.post(
        f"{BASE}/sow/{sow_id}/commercial-details/businessContext/validate",
        json=payload,
    )
    assert v.status_code == 200
    assert v.json().get("valid") is True


@pytest.mark.asyncio
async def test_manual_generation_preview_includes_ai_derived_fields(client_auth):
    client, _uid = client_auth
    files = {"file": ("ai.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")}
    data = {"projectTitle": "AI Enrichment Project", "clientOrganisation": "ACME"}
    up = await client.post(f"{BASE}/sow/upload", files=files, data=data)
    if up.status_code != 200:
        pytest.skip(f"MongoDB or storage required: {up.status_code} {up.text}")
    sow_id = up.json()["sow_id"]

    # Wait for extraction completion.
    for _ in range(60):
        st = await client.get(f"{BASE}/sow/{sow_id}/upload-status")
        assert st.status_code == 200, st.text
        state = st.json().get("processing_state")
        if state == "complete":
            break
        await asyncio.sleep(0.15)
    else:
        pytest.fail("Upload/extraction did not complete in time")

    # Ensure generation precondition for accepted features.
    accept = await client.post(f"{BASE}/sow/{sow_id}/extraction-items/accept-all")
    assert accept.status_code == 200, accept.text

    section_payloads = {
        "businessContext": {
            "projectVision": "Deliver a production-grade workflow platform that improves team throughput and reliability." * 2,
            "businessCriticality": "standard",
            "currentState": "Current workflow is fragmented across tools.",
            "desiredFutureState": "Unified process with automation and clear accountability.",
            "definitionOfSuccess": "Stakeholders approve outcomes with measurable cycle-time reduction.",
        },
        "deliveryScope": {
            "platformType": "WEB_APPLICATION",
            "developmentScope": ["Backend", "API", "Integration"],
            "uiuxDesignScope": "in_scope",
            "deploymentScope": "cloud",
            "goLiveScope": "go_live",
            "dataMigrationScope": "not_in_scope",
        },
        "techIntegrations": {
            "technologyStack": "Python FastAPI React PostgreSQL with cloud deployment and API integrations.",
        },
        "timelineTeam": {
            "startDate": "2026-01-01",
            "targetEndDate": "2026-06-30",
            "uatSignOffAuthority": "Jane Doe",
            "uatSignOffConfirmed": True,
        },
        "budgetRisk": {
            "budgetMinimum": 10000,
            "budgetMaximum": 20000,
            "pricingModel": "fixed_price",
        },
        "governance": {
            "nonDiscriminationConfirmed": True,
            "dataSensitivityLevel": "internal",
            "personalDataInvolved": "no",
        },
        "commercialLegal": {
            "ipOwnership": "client_owns_all",
            "sourceCodeOwnership": "client_hosts",
            "changeRequestProcess": "formal_cr",
            "thirdPartyCosts": "client_pays",
        },
    }
    for section, payload in section_payloads.items():
        p = await client.patch(f"{BASE}/sow/{sow_id}/commercial-details/{section}", json=payload)
        assert p.status_code == 200, p.text
        m = await client.post(
            f"{BASE}/sow/{sow_id}/commercial-details/sections/mark-complete",
            json={"section": section},
        )
        assert m.status_code == 200, m.text

    approvers = {
        "business_owner_approver": "bo@example.com",
        "final_approver": "fa@example.com",
    }
    a = await client.patch(f"{BASE}/sow/{sow_id}/approval-authorities", json=approvers)
    assert a.status_code == 200, a.text

    g = await client.post(f"{BASE}/sow/{sow_id}/generate", json={"include_extracted_sections": True})
    assert g.status_code == 202, g.text

    for _ in range(80):
        gs = await client.get(f"{BASE}/sow/{sow_id}/generation-status")
        assert gs.status_code == 200, gs.text
        g_status = gs.json().get("status")
        if g_status == "complete":
            break
        if g_status == "error":
            pytest.fail(f"Generation failed: {gs.json()}")
        await asyncio.sleep(0.15)
    else:
        pytest.fail("Generation did not complete in time")

    preview = await client.get(f"{BASE}/sow/{sow_id}/preview")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert isinstance(body.get("hallucination_analysis"), list)
    assert len(body.get("hallucination_analysis") or []) >= 1
    assert isinstance(body.get("ai_parse_insights"), dict)
    assert (body.get("ai_parse_insights") or {}).get("sections_found") is not None
    qm = body.get("quality_metrics") or {}
    assert qm.get("confidence") is not None
    assert qm.get("risk_score") is not None
    assert qm.get("hallucination_flags") is not None


@pytest.mark.asyncio
async def test_wizard_shape_adapter_builds_steps():
    from app.services.manual_sow.wizard_shape_adapter import build_wizard_data_from_manual

    commercial = {
        "businessContext": {
            "projectVision": "A" * 50,
            "businessCriticality": "standard",
            "currentState": "x",
            "desiredFutureState": "y",
            "definitionOfSuccess": "z",
        },
        "deliveryScope": {
            "platformType": "FULL_STACK",
            "developmentScope": ["Backend"],
            "uiuxDesignScope": "not_in_scope",
            "deploymentScope": "cloud",
            "goLiveScope": "go_live",
            "dataMigrationScope": "not_in_scope",
        },
        "techIntegrations": {"technologyStack": "Python FastAPI React"},
        "timelineTeam": {
            "startDate": "2026-01-01",
            "targetEndDate": "2026-12-31",
            "uatSignOffAuthority": "Jane Doe",
            "uatSignOffConfirmed": True,
        },
        "budgetRisk": {
            "budgetMinimum": 10000,
            "budgetMaximum": 50000,
            "currency": "USD",
            "pricingModel": "fixed_price",
        },
        "governance": {
            "nonDiscriminationConfirmed": True,
            "dataSensitivityLevel": "internal",
            "personalDataInvolved": "no",
        },
        "commercialLegal": {
            "ipOwnership": "client_owns_all",
            "sourceCodeOwnership": "client_hosts",
            "changeRequestProcess": "formal_cr",
            "thirdPartyCosts": "client_pays",
        },
    }
    wd = build_wizard_data_from_manual(
        title="T",
        client="C",
        commercial_details=commercial,
        feature_module_texts=["Feature A description here"],
    )
    assert "step_0" in wd and "step_8" in wd
    from app.services.sow_generator import generate_sow_content

    out = generate_sow_content(wd)
    assert out.get("sections")


def test_commercial_prefill_from_extraction_passes_section_validation():
    """AI prefill for businessContext + techIntegrations must satisfy validate_section for mark-complete."""
    from app.services.manual_sow.commercial_prefill import build_commercial_prefill_from_extraction
    from app.services.manual_sow.commercial_validation import validate_section
    from app.schemas.manual_sow.enums import CommercialSectionKey

    items = [
        {"category": "business_objectives", "text": "Grow revenue by 20% in fiscal year through digital channels."},
        {"category": "features", "text": "Python FastAPI backend with React frontend and PostgreSQL database."},
    ]
    report = {"contextDetection": {"businessObjectives": "PRESENT"}, "platformType": "WEB_APPLICATION"}
    bc, ti, ds = build_commercial_prefill_from_extraction(items, report, title="Proj", client="Org")
    assert ds.get("platformType") == "WEB_APPLICATION"
    assert isinstance(ds.get("developmentScope"), list) and len(ds["developmentScope"]) >= 1
    ok, err = validate_section(CommercialSectionKey.businessContext, bc)
    assert ok, err
    ok2, err2 = validate_section(CommercialSectionKey.techIntegrations, ti)
    assert ok2, err2
    ok3, err3 = validate_section(CommercialSectionKey.deliveryScope, ds)
    assert ok3, err3


def test_merge_delivery_scope_repair_fixes_invalid_existing_values():
    """Invalid-but-present enums must be replaced by seed so mark-complete prefill works."""
    from app.services.manual_sow.commercial_prefill import (
        build_commercial_prefill_from_extraction,
        merge_commercial_details_prefill,
    )
    from app.services.manual_sow.commercial_validation import validate_section
    from app.schemas.manual_sow.enums import CommercialSectionKey

    items = [
        {"category": "features", "text": "React frontend and FastAPI backend deployed on AWS."},
    ]
    report = {"platformType": "WEB_APPLICATION"}
    _, _, seed_ds = build_commercial_prefill_from_extraction(items, report, title="P", client="C")
    bad_cd = {
        "deliveryScope": {
            "platformType": "WEB_APPLICATION",
            "developmentScope": [],
            "uiuxDesignScope": "In Scope",
            "deploymentScope": "cloud_hosted",
            "goLiveScope": "live",
            "dataMigrationScope": "yes",
        }
    }
    merged = merge_commercial_details_prefill(bad_cd, {}, {}, seed_ds)
    ok, err = validate_section(CommercialSectionKey.deliveryScope, merged["deliveryScope"])
    assert ok, err
    assert len(merged["deliveryScope"]["developmentScope"]) >= 1


@pytest.mark.asyncio
async def test_gate_features_required():
    from app.services.manual_sow.gates import gate_step3_to_4

    assert not gate_step3_to_4([{"category": "features", "review_state": "pending"}])
    assert gate_step3_to_4([{"category": "features", "review_state": "accepted"}])


def test_commercial_legal_validation_without_warranty_period():
    from app.schemas.manual_sow.enums import CommercialSectionKey
    from app.services.manual_sow.commercial_validation import validate_section

    payload = {
        "ipOwnership": "client_owns_all",
        "sourceCodeOwnership": "client_hosts",
        "changeRequestProcess": "formal_cr",
        "thirdPartyCosts": "client_pays",
        "finalApprover": "ignored@example.com",
    }
    ok, errors = validate_section(CommercialSectionKey.commercialLegal, payload)
    assert ok, errors

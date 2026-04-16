import importlib
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

BASE = "/api/v1"


def _load_main():
    os.environ["BILLING_API_ENABLED"] = "false"
    os.environ["REVIEWER_API_ENABLED"] = "false"

    import app.core.config as config_module

    importlib.reload(config_module)
    import app.main as main_module

    return importlib.reload(main_module)


@pytest.fixture
def main_module():
    return _load_main()


def test_project_portfolio_routes_registered(main_module):
    paths = {route.path for route in main_module.app.routes}
    assert f"{BASE}/portfolio/projects" in paths
    assert f"{BASE}/portfolio/export" in paths
    assert f"{BASE}/projects/kickoff" in paths
    assert f"{BASE}/projects/{{project_id}}/timeline" in paths
    assert f"{BASE}/projects/{{project_id}}/payments/pending" in paths
    assert f"{BASE}/milestones/{{milestone_id}}" in paths
    assert f"{BASE}/evidence/{{evidence_id}}" in paths
    assert f"{BASE}/projects/{{project_id}}/commercial" in paths
    assert f"{BASE}/auth/send-otp" in paths
    assert f"{BASE}/escalations" in paths


@pytest.mark.asyncio
async def test_project_portfolio_endpoints_smoke(main_module):
    async with AsyncClient(transport=ASGITransport(app=main_module.app), base_url="http://test") as client:
        summary = await client.get(f"{BASE}/portfolio/summary-metrics")
        assert summary.status_code == 200, summary.text
        assert summary.json()["total_projects"] >= 4

        project_list = await client.get(
            f"{BASE}/portfolio/projects",
            params={"status": "active,REWORK", "sort_by": "completion"},
        )
        assert project_list.status_code == 200, project_list.text
        assert len(project_list.json()["projects"]) >= 1

        completed = await client.get(f"{BASE}/projects/completed")
        assert completed.status_code == 200, completed.text

        overview = await client.get(f"{BASE}/projects/proj_001/overview")
        assert overview.status_code == 200, overview.text
        assert overview.json()["project_id"] == "proj_001"

        activities = await client.get(f"{BASE}/projects/proj_001/activities")
        assert activities.status_code == 200, activities.text
        assert len(activities.json()["activities"]) >= 1

        timeline = await client.get(
            f"{BASE}/projects/proj_001/timeline",
            params={"view": "gantt"},
        )
        assert timeline.status_code == 200, timeline.text
        assert timeline.json()["project_id"] == "proj_001"

        evidence_packs = await client.get(
            f"{BASE}/projects/proj_001/evidence-packs",
            params={"status": "PENDING_REVIEW", "page": 1, "limit": 10},
        )
        assert evidence_packs.status_code == 200, evidence_packs.text
        assert evidence_packs.json()["project_id"] == "proj_001"

        evidence_detail = await client.get(f"{BASE}/evidence/ep_p1_01")
        assert evidence_detail.status_code == 200, evidence_detail.text
        assert evidence_detail.json()["id"] == "ep_p1_01"

        rework = await client.get(
            f"{BASE}/projects/proj_001/rework-requests",
            params={"status": "OPEN", "page": 1, "limit": 10},
        )
        assert rework.status_code == 200, rework.text
        assert rework.json()["project_id"] == "proj_001"

        exceptions_before = await client.get(f"{BASE}/projects/proj_001/exceptions")
        assert exceptions_before.status_code == 200, exceptions_before.text

        create_exception = await client.post(
            f"{BASE}/projects/proj_001/exceptions",
            json={
                "type": "PAYMENT_BLOCKER",
                "severity": "HIGH",
                "title": "Release approval delayed",
                "detail": "Finance reviewer is awaiting one last artifact.",
            },
        )
        assert create_exception.status_code == 200, create_exception.text
        assert create_exception.json()["project_id"] == "proj_001"

        project_detail = await client.get(f"{BASE}/projects/proj_001")
        assert project_detail.status_code == 200, project_detail.text

        milestone_detail = await client.get(f"{BASE}/milestones/ms_proj_001_m1")
        assert milestone_detail.status_code == 200, milestone_detail.text
        assert milestone_detail.json()["project_id"] == "proj_001"

        team = await client.get(f"{BASE}/projects/proj_001/team-composition")
        assert team.status_code == 200, team.text
        assert team.json()["project_id"] == "proj_001"

        skill_coverage = await client.get(f"{BASE}/projects/proj_001/skill-coverage")
        assert skill_coverage.status_code == 200, skill_coverage.text
        assert skill_coverage.json()["project_id"] == "proj_001"

        skill_review = await client.post(
            f"{BASE}/projects/proj_001/skill-review-request",
            json={"note": "Please verify coverage for the QA stage."},
        )
        assert skill_review.status_code == 200, skill_review.text
        assert skill_review.json()["project_id"] == "proj_001"

        pending_payments = await client.get(f"{BASE}/projects/proj_001/payments/pending")
        assert pending_payments.status_code == 200, pending_payments.text
        assert any(item["payment_id"] == "pay_p1_01" for item in pending_payments.json()["pending"])

        payment_otp = await client.post(f"{BASE}/projects/proj_001/payments/pay_p1_01/send-otp")
        assert payment_otp.status_code == 200, payment_otp.text
        demo_otp = payment_otp.json()["demo_otp"]

        release_payment = await client.get(
            f"{BASE}/projects/proj_001/payments/pay_p1_01/release",
            params={"otp": demo_otp},
        )
        assert release_payment.status_code == 200, release_payment.text
        assert release_payment.json()["status"] == "released"

        payment_history = await client.get(f"{BASE}/projects/proj_001/payments/history")
        assert payment_history.status_code == 200, payment_history.text
        assert any(item["payment_id"] == "pay_p1_01" for item in payment_history.json()["payments"])

        hold_payment = await client.post(
            f"{BASE}/projects/proj_001/payments/pay_p1_02/hold",
            json={"note": "Manual review requested."},
        )
        assert hold_payment.status_code == 200, hold_payment.text
        assert hold_payment.json()["status"] == "on_hold"

        new_project_id = f"proj_portfolio_{uuid.uuid4().hex[:8]}"
        kickoff = await client.post(
            f"{BASE}/projects/kickoff",
            json={
                "project_id": new_project_id,
                "name": "Portfolio smoke project",
                "summary": "Created during automated smoke coverage.",
                "owner": "Smoke Test",
            },
        )
        assert kickoff.status_code == 200, kickoff.text
        assert kickoff.json()["id"] == new_project_id

        project_summary = await client.get(f"{BASE}/portfolio/project-summary/{new_project_id}")
        assert project_summary.status_code == 200, project_summary.text
        assert project_summary.json()["id"] == new_project_id

        status_update = await client.post(
            f"{BASE}/projects/{new_project_id}/status",
            json={"to_status": "IN_PROGRESS", "actor_role": "manager"},
        )
        assert status_update.status_code == 200, status_update.text
        assert status_update.json()["status"] == "IN_PROGRESS"

        hold_project = await client.post(f"{BASE}/projects/{new_project_id}/hold")
        assert hold_project.status_code == 200, hold_project.text
        assert hold_project.json()["on_hold"] is True

        resume_project = await client.post(f"{BASE}/projects/{new_project_id}/resume")
        assert resume_project.status_code == 200, resume_project.text
        assert resume_project.json()["on_hold"] is False

        project_report = await client.get(f"{BASE}/projects/{new_project_id}/report")
        assert project_report.status_code == 200, project_report.text
        assert project_report.headers["content-type"].startswith("text/csv")

        portfolio_export = await client.get(f"{BASE}/portfolio/export")
        assert portfolio_export.status_code == 200, portfolio_export.text
        assert portfolio_export.headers["content-type"].startswith("text/csv")

        commercial = await client.get(f"{BASE}/projects/{new_project_id}/commercial")
        assert commercial.status_code == 200, commercial.text
        assert commercial.json()["project_id"] == new_project_id

        send_m2_otp = await client.post(
            f"{BASE}/auth/send-otp",
            json={"purpose": "m2_payment", "project_id": new_project_id},
        )
        assert send_m2_otp.status_code == 200, send_m2_otp.text
        m2_payload = send_m2_otp.json()

        confirm_m2 = await client.post(
            f"{BASE}/payments/milestone/m2/{new_project_id}/confirm",
            json={
                "otp": m2_payload["demo_otp"],
                "challenge_id": m2_payload["challenge_id"],
            },
        )
        assert confirm_m2.status_code == 200, confirm_m2.text
        assert confirm_m2.json()["status"] == "m2_otp_verified"

        release_m2 = await client.post(f"{BASE}/payments/milestone/m2/{new_project_id}/release")
        assert release_m2.status_code == 200, release_m2.text
        assert release_m2.json()["status"] == "m2_payment_released"

        start_uat = await client.post(f"{BASE}/projects/{new_project_id}/uat-signoff")
        assert start_uat.status_code == 200, start_uat.text
        uat_payload = start_uat.json()

        confirm_uat = await client.post(
            f"{BASE}/projects/{new_project_id}/uat-signoff/confirm",
            json={
                "otp": uat_payload["demo_otp"],
                "challenge_id": uat_payload["challenge_id"],
            },
        )
        assert confirm_uat.status_code == 200, confirm_uat.text
        assert confirm_uat.json()["status"] == "m3_invoice_triggered"

        escalation = await client.post(
            f"{BASE}/escalations",
            json={
                "project_id": new_project_id,
                "reason": "Dependency owner missed handoff.",
                "severity": "HIGH",
            },
        )
        assert escalation.status_code == 200, escalation.text
        assert escalation.json()["project_id"] == new_project_id

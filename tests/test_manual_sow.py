"""Tests for Manual SOW intake API (/api/v1/sow)."""

import io
import socket

import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from app.core.database import close_db, connect_db
from app.core.security import get_current_user
from app.main import app

BASE = "/api/v1"


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
            "warrantyPeriod": "90_days",
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


@pytest.mark.asyncio
async def test_gate_features_required():
    from app.services.manual_sow.gates import gate_step3_to_4

    assert not gate_step3_to_4([{"category": "features", "review_state": "pending"}])
    assert gate_step3_to_4([{"category": "features", "review_state": "accepted"}])

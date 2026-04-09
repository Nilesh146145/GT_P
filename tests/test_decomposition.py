"""Decomposition / Planning §8 API — Mongo-backed lifecycle."""

import importlib
import os
import socket
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from app.core.database import close_db, connect_db, get_decomposition_plans_collection, get_users_collection
from app.core.security import create_access_token, get_password_hash

BASE = "/api/v1"


def _mongo_listening(host: str = "127.0.0.1", port: int = 27017, timeout: float = 0.4) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _load_main():
    import app.core.config as config_module
    import app.main as main_module

    importlib.reload(config_module)
    return importlib.reload(main_module)


async def _insert_user(*, email: str, role: str, extra: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    document = {
        "email": email.lower(),
        "hashed_password": get_password_hash("TestPass123"),
        "first_name": "Test",
        "last_name": role.title(),
        "full_name": f"Test {role.title()}",
        "role": role,
        "provider": "credentials",
        "mfa_enabled": True,
        "requires_password_change": False,
        "is_first_login": False,
        "email_verified": True,
        "phone_verified": False,
        "created_at": now,
        "updated_at": now,
    }
    if extra:
        document.update(extra)
    result = await get_users_collection().insert_one(document)
    document["_id"] = result.inserted_id
    document["id"] = str(result.inserted_id)
    return document


def _auth_headers(user_id: str, role: str) -> dict[str, str]:
    token = create_access_token({"sub": user_id, "role": role}, mfa_verified=True)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def deco_client():
    if not _mongo_listening():
        pytest.skip("MongoDB not reachable on localhost:27017")
    os.environ["DECOMPOSITION_REVISION_WEBHOOK_SECRET"] = "test-deco-webhook-secret"
    main_module = _load_main()
    await connect_db()
    await main_module.create_indexes()
    try:
        async with AsyncClient(transport=ASGITransport(app=main_module.app), base_url="http://test") as client:
            yield client
    finally:
        await close_db()


@pytest.mark.asyncio
async def test_decomposition_kickoff_gate_confirm_revision_flow(deco_client: AsyncClient):
    user = await _insert_user(
        email=f"ent_deco_{uuid.uuid4().hex[:8]}@test.com",
        role="enterprise",
        extra={"enterprise_profile_id": str(ObjectId())},
    )
    headers = _auth_headers(user["id"], "enterprise")
    eid = user["enterprise_profile_id"]

    create_res = await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans",
        headers=headers,
        json={
            "sow_reference": "SOW-100",
            "project_name": "Alpha",
            "sow_version": "2",
            "sow_start": "2026-04-01",
            "sow_end": "2026-04-10",
        },
    )
    assert create_res.status_code == 200, create_res.text
    plan_id = create_res.json()["plan_id"]

    list_res = await deco_client.get(f"{BASE}/enterprise/decomposition/plans", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json() == []

    g403 = await deco_client.get(f"{BASE}/enterprise/decomposition/plans/{plan_id}", headers=headers)
    assert g403.status_code == 403
    assert "kicked off" in g403.json()["detail"].lower()

    ko = await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans/actions/kickoff",
        headers=headers,
        params={"plan_id": plan_id},
    )
    assert ko.status_code == 200, ko.text

    list2 = await deco_client.get(f"{BASE}/enterprise/decomposition/plans", headers=headers)
    assert len(list2.json()) == 1

    g200 = await deco_client.get(f"{BASE}/enterprise/decomposition/plans/{plan_id}", headers=headers)
    assert g200.status_code == 200
    body = g200.json()
    assert body["status"] == "PLAN_REVIEW_REQUIRED"

    bad_confirm = await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans/{plan_id}/confirm",
        headers=headers,
        json={"confirmed_by": user["id"]},
    )
    assert bad_confirm.status_code == 400

    await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans/{plan_id}/checklist",
        headers=headers,
        json={"item1": True, "item2": True, "item3": True},
    )

    ok_confirm = await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans/{plan_id}/confirm",
        headers=headers,
        json={"confirmed_by": user["id"]},
    )
    assert ok_confirm.status_code == 200, ok_confirm.text

    twice = await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans/{plan_id}/confirm",
        headers=headers,
        json={"confirmed_by": user["id"]},
    )
    assert twice.status_code == 400

    lock = await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans/{plan_id}/lock",
        headers=headers,
        json={"contributor_id": "contrib-1", "assignment_offer_id": "offer-1"},
    )
    assert lock.status_code == 200, lock.text

    col = get_decomposition_plans_collection()
    await col.delete_many({"plan_id": plan_id})
    await get_users_collection().delete_one({"_id": user["_id"]})


@pytest.mark.asyncio
async def test_revision_notes_dcp003_and_webhook_complete(deco_client: AsyncClient):
    user = await _insert_user(
        email=f"ent_deco2_{uuid.uuid4().hex[:8]}@test.com",
        role="enterprise",
        extra={"enterprise_profile_id": str(ObjectId())},
    )
    headers = _auth_headers(user["id"], "enterprise")

    create_res = await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans",
        headers=headers,
        json={"sow_reference": "SOW-200", "project_name": "Beta"},
    )
    plan_id = create_res.json()["plan_id"]
    await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans/actions/kickoff",
        headers=headers,
        params={"plan_id": plan_id},
    )

    short = await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans/{plan_id}/request-revision",
        headers=headers,
        json={"requested_by": user["id"], "revision_notes": "too short"},
    )
    assert short.status_code == 422

    rev = await deco_client.post(
        f"{BASE}/enterprise/decomposition/plans/{plan_id}/request-revision",
        headers=headers,
        json={
            "requested_by": user["id"],
            "revision_notes": "x" * 30 + " need more detail on milestone two API tasks.",
        },
    )
    assert rev.status_code == 200, rev.text
    assert rev.json()["new_status"] == "REVISION_IN_PROGRESS"

    bad_wh = await deco_client.post(
        f"{BASE}/internal/decomposition/plans/{plan_id}/revision/complete",
        headers={"X-GT-Decomposition-Webhook-Secret": "wrong"},
        json={},
    )
    assert bad_wh.status_code == 403

    ok_wh = await deco_client.post(
        f"{BASE}/internal/decomposition/plans/{plan_id}/revision/complete",
        headers={"X-GT-Decomposition-Webhook-Secret": "test-deco-webhook-secret"},
        json={},
    )
    assert ok_wh.status_code == 200, ok_wh.text

    st = await deco_client.get(f"{BASE}/enterprise/decomposition/plans/{plan_id}/status", headers=headers)
    assert st.json()["status"] == "PLAN_REVIEW_REQUIRED"

    revised = await deco_client.get(f"{BASE}/enterprise/decomposition/plans/{plan_id}/revised", headers=headers)
    assert revised.status_code == 200

    col = get_decomposition_plans_collection()
    await col.delete_many({"plan_id": plan_id})
    await get_users_collection().delete_one({"_id": user["_id"]})

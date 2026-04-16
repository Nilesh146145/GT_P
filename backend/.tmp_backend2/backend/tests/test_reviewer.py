"""
Reviewer API — dashboard, queue, assignment PATCH, evidence recommend, admin assign/list.
"""

import uuid

import pyotp
import pytest
import pytest_asyncio

BASE = "/api/v1"


async def _provision_active_reviewer(client) -> dict:
    """Register, flip to reviewer + MFA in DB, return JWT headers and Mongo user id."""
    email = f"rev_{uuid.uuid4().hex[:10]}@test.com"
    r = await client.post(f"{BASE}/auth/register", json=_register_json(email))
    assert r.status_code == 201, r.text
    from app.core.database import get_users_collection

    col = get_users_collection()
    user = await col.find_one({"email": email.lower()})
    uid = str(user["_id"])
    secret = "JBSWY3DPEHPK3PXP"
    await col.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "role": "reviewer",
                "requires_password_change": False,
                "mfa_secret": secret,
                "is_mfa_enabled": True,
                "mfa_enabled": True,
                "mfa_recovery_hashes": [],
            }
        },
    )
    lr = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    assert lr.status_code == 200, lr.text
    code = pyotp.TOTP(secret).now()
    mfa = await client.post(
        f"{BASE}/auth/mfa/verify",
        json={"email": email, "code": code, "rememberMe": False},
    )
    assert mfa.status_code == 200, mfa.text
    return {
        "headers": {"Authorization": f"Bearer {mfa.json()['access_token']}"},
        "user_id": uid,
        "email": email,
    }


def _register_json(email: str, password: str = "testpassword123") -> dict:
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


@pytest_asyncio.fixture
async def admin_headers(client):
    email = f"adm_{uuid.uuid4().hex[:10]}@test.com"
    r = await client.post(f"{BASE}/auth/register", json=_register_json(email))
    assert r.status_code == 201, r.text
    from app.core.database import get_users_collection

    col = get_users_collection()
    user = await col.find_one({"email": email.lower()})
    await col.update_one({"_id": user["_id"]}, {"$set": {"role": "admin"}})
    lr = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    assert lr.status_code == 200, lr.text
    token = lr.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def enterprise_headers(client):
    """JWT for a normal enterprise registration (role ``enterprise`` in DB, unchanged)."""
    email = f"ent_{uuid.uuid4().hex[:10]}@test.com"
    r = await client.post(f"{BASE}/auth/register", json=_register_json(email))
    assert r.status_code == 201, r.text
    lr = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    assert lr.status_code == 200, lr.text
    token = lr.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def reviewer_bundle(client):
    """Active reviewer JWT + user id (MFA satisfied with known TOTP secret)."""
    return await _provision_active_reviewer(client)


@pytest.mark.asyncio
async def test_reviewer_dashboard_unauthorized(client):
    res = await client.get(f"{BASE}/reviewer/dashboard")
    assert res.status_code == 403 or res.status_code == 401


@pytest.mark.asyncio
async def test_reviewer_dashboard_and_projects(client, reviewer_bundle):
    h = reviewer_bundle["headers"]
    d = await client.get(f"{BASE}/reviewer/dashboard", headers=h)
    assert d.status_code == 200
    body = d.json()
    assert body.get("success") is True
    data = body["data"]
    assert "assignedTaskCount" in data
    assert "pendingEvidenceReviews" in data
    assert "completedLast30Days" in data
    assert "evidenceApprovalRatePercent" in data

    p = await client.get(f"{BASE}/reviewer/projects", headers=h)
    assert p.status_code == 200
    assert isinstance(p.json().get("data"), list)


@pytest.mark.asyncio
async def test_enterprise_can_assign_reviewer_tasks(client, enterprise_headers, reviewer_bundle):
    rid = reviewer_bundle["user_id"]
    create = await client.post(
        f"{BASE}/users/reviewers/{rid}/assignments",
        headers=enterprise_headers,
        json={"title": "From enterprise admin", "taskKind": "project"},
    )
    assert create.status_code == 201, create.text


@pytest.mark.asyncio
async def test_reviewer_can_self_assign_and_list(client, reviewer_bundle):
    rid = reviewer_bundle["user_id"]
    rh = reviewer_bundle["headers"]
    create = await client.post(
        f"{BASE}/users/reviewers/{rid}/assignments",
        headers=rh,
        json={"title": "Self-serve task", "taskKind": "project"},
    )
    assert create.status_code == 201, create.text
    aid = create.json()["data"]["id"]
    lst = await client.get(f"{BASE}/users/reviewers/{rid}/assignments", headers=rh)
    assert lst.status_code == 200
    assert any(x["id"] == aid for x in lst.json()["data"])


@pytest.mark.asyncio
async def test_reviewer_cannot_assign_tasks_for_other_reviewer(client, reviewer_bundle):
    other = await _provision_active_reviewer(client)
    rh = reviewer_bundle["headers"]
    denied = await client.post(
        f"{BASE}/users/reviewers/{other['user_id']}/assignments",
        headers=rh,
        json={"title": "Should fail", "taskKind": "project"},
    )
    assert denied.status_code == 403
    assert "own queue" in denied.json()["detail"].lower() or "role" in denied.json()["detail"].lower()


@pytest.mark.asyncio
async def test_legacy_enterprise_user_role_can_assign(client, reviewer_bundle):
    """``enterprise_user`` and whitespace role values normalize to enterprise."""
    email = f"leg_{uuid.uuid4().hex[:10]}@test.com"
    r = await client.post(f"{BASE}/auth/register", json=_register_json(email))
    assert r.status_code == 201
    from app.core.database import get_users_collection

    col = get_users_collection()
    user = await col.find_one({"email": email.lower()})
    await col.update_one({"_id": user["_id"]}, {"$set": {"role": "enterprise_user"}})
    lr = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    assert lr.status_code == 200
    eh = {"Authorization": f"Bearer {lr.json()['access_token']}"}
    rid = reviewer_bundle["user_id"]
    create = await client.post(
        f"{BASE}/users/reviewers/{rid}/assignments",
        headers=eh,
        json={"title": "Legacy role label", "taskKind": "project"},
    )
    assert create.status_code == 201, create.text


@pytest.mark.asyncio
async def test_admin_assign_list_patch_and_evidence(client, admin_headers, reviewer_bundle):
    rid = reviewer_bundle["user_id"]
    ah = admin_headers
    rh = reviewer_bundle["headers"]

    create = await client.post(
        f"{BASE}/users/reviewers/{rid}/assignments",
        headers=ah,
        json={"title": "Q1 audit", "taskKind": "project"},
    )
    assert create.status_code == 201, create.text
    aid = create.json()["data"]["id"]

    lst = await client.get(f"{BASE}/users/reviewers/{rid}/assignments", headers=ah)
    assert lst.status_code == 200
    assert any(x["id"] == aid for x in lst.json()["data"])

    patch = await client.patch(
        f"{BASE}/reviewer/assignments/{aid}",
        headers=rh,
        json={"status": "in_progress"},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["data"]["status"] == "in_progress"

    done = await client.patch(
        f"{BASE}/reviewer/assignments/{aid}",
        headers=rh,
        json={"status": "completed"},
    )
    assert done.status_code == 200
    assert done.json()["data"]["status"] == "completed"

    ev_id = f"ev_{uuid.uuid4().hex[:8]}"
    ev_asg = await client.post(
        f"{BASE}/users/reviewers/{rid}/assignments",
        headers=ah,
        json={
            "title": "Evidence pack",
            "taskKind": "evidence_review",
            "relatedId": ev_id,
        },
    )
    assert ev_asg.status_code == 201
    ev_aid = ev_asg.json()["data"]["id"]

    bad = await client.patch(
        f"{BASE}/reviewer/assignments/{ev_aid}",
        headers=rh,
        json={"status": "completed"},
    )
    assert bad.status_code == 400

    rec = await client.post(
        f"{BASE}/reviewer/evidence/{ev_id}/recommend",
        headers=rh,
        json={"score": 88, "comment": "Looks good.", "recommendation": "ACCEPT"},
    )
    assert rec.status_code == 200, rec.text

    projects = await client.get(f"{BASE}/reviewer/projects", headers=rh)
    ev_row = next(x for x in projects.json()["data"] if x["id"] == ev_aid)
    assert ev_row["status"] == "completed"

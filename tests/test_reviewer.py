import importlib
import os
import socket
import uuid
from datetime import datetime, timezone

import pyotp
import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from app.core.database import close_db, connect_db, get_users_collection
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


def _load_main(enabled: bool):
    os.environ["REVIEWER_API_ENABLED"] = "true" if enabled else "false"
    import app.main as main_module

    return importlib.reload(main_module)


async def _insert_user(
    *,
    email: str,
    role: str,
    password: str = "AdminPass123",
    mfa_enabled: bool = True,
    requires_password_change: bool = False,
    extra: dict | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    document = {
        "email": email.lower(),
        "hashed_password": get_password_hash(password),
        "first_name": "Test",
        "last_name": role.title(),
        "full_name": f"Test {role.title()}",
        "role": role,
        "provider": "credentials",
        "mfa_enabled": mfa_enabled,
        "requires_password_change": requires_password_change,
        "is_first_login": requires_password_change,
        "email_verified": False,
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


def _reviewer_payload(email: str) -> dict:
    return {
        "email": email,
        "firstName": "Ria",
        "lastName": "Reviewer",
        "role": "Lead Reviewer",
        "designation": "Quality Lead",
        "department": "Governance",
        "username": f"rev_{uuid.uuid4().hex[:8]}",
        "language": "en",
        "timeZone": "Asia/Calcutta",
        "status": "INVITED",
    }


@pytest.fixture
def main_module_disabled():
    return _load_main(False)


@pytest_asyncio.fixture
async def main_module_enabled():
    if not _mongo_listening():
        pytest.skip("MongoDB not reachable on localhost:27017")
    module = _load_main(True)
    await connect_db()
    await module.create_indexes()
    try:
        yield module
    finally:
        await close_db()


@pytest_asyncio.fixture
async def client(main_module_enabled):
    async with AsyncClient(transport=ASGITransport(app=main_module_enabled.app), base_url="http://test") as api_client:
        yield api_client


async def _provision_enterprise_admin() -> tuple[dict, dict[str, str]]:
    user = await _insert_user(
        email=f"enterprise_{uuid.uuid4().hex[:8]}@test.com",
        role="enterprise",
        mfa_enabled=True,
        extra={"enterprise_profile_id": str(ObjectId())},
    )
    return user, _auth_headers(user["id"], "enterprise")


async def _create_active_reviewer(client: AsyncClient, admin_headers: dict[str, str]) -> dict:
    email = f"reviewer_{uuid.uuid4().hex[:8]}@test.com"
    create_res = await client.post(f"{BASE}/users", headers=admin_headers, json=_reviewer_payload(email))
    assert create_res.status_code == 201, create_res.text
    create_body = create_res.json()["data"]
    temp_password = create_body["temporaryPassword"]
    reviewer_user_id = create_body["id"]

    login_res = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": temp_password},
    )
    assert login_res.status_code == 200, login_res.text
    assert login_res.json()["status"] == "mfa_setup_required"
    pending_token = login_res.json()["mfa_pending_token"]

    init_res = await client.post(
        f"{BASE}/auth/mfa/setup/init",
        headers={"Authorization": f"Bearer {pending_token}"},
    )
    assert init_res.status_code == 200, init_res.text
    secret = init_res.json()["secret_base32"]

    confirm_res = await client.post(
        f"{BASE}/auth/mfa/setup/confirm",
        headers={"Authorization": f"Bearer {pending_token}"},
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert confirm_res.status_code == 200, confirm_res.text
    setup_access = confirm_res.json()["access_token"]

    me_before = await client.get(
        f"{BASE}/auth/me",
        headers={"Authorization": f"Bearer {setup_access}"},
    )
    assert me_before.status_code == 200, me_before.text
    assert me_before.json()["requiresPasswordChange"] is True
    assert me_before.json()["mfaEnabled"] is True

    new_password = "ReviewerPass123"
    change_res = await client.post(
        f"{BASE}/auth/password/change",
        headers={"Authorization": f"Bearer {setup_access}"},
        json={"current_password": temp_password, "new_password": new_password},
    )
    assert change_res.status_code == 200, change_res.text

    login_again = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": new_password},
    )
    assert login_again.status_code == 200, login_again.text
    assert login_again.json()["status"] == "mfa_required"
    verify_res = await client.post(
        f"{BASE}/auth/mfa/verify",
        headers={"Authorization": f"Bearer {login_again.json()['mfa_pending_token']}"},
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert verify_res.status_code == 200, verify_res.text
    return {
        "email": email,
        "user_id": reviewer_user_id,
        "secret": secret,
        "headers": {"Authorization": f"Bearer {verify_res.json()['access_token']}"},
    }


def test_reviewer_routes_not_registered_when_flag_disabled(main_module_disabled):
    paths = {route.path for route in main_module_disabled.app.routes}
    assert f"{BASE}/reviewer/dashboard" not in paths
    assert f"{BASE}/users/reviewers/{{reviewer_user_id}}/assignments" not in paths


@pytest.mark.asyncio
async def test_reviewer_onboarding_requires_mfa_and_password_change(client: AsyncClient):
    _, admin_headers = await _provision_enterprise_admin()
    reviewer = await _create_active_reviewer(client, admin_headers)

    me_after = await client.get(f"{BASE}/auth/me", headers=reviewer["headers"])
    assert me_after.status_code == 200, me_after.text
    body = me_after.json()
    assert body["role"] == "reviewer"
    assert body["requiresPasswordChange"] is False
    assert body["mfaEnabled"] is True
    assert body["mfaEnrollmentRequired"] is False

    dashboard = await client.get(f"{BASE}/reviewer/dashboard", headers=reviewer["headers"])
    assert dashboard.status_code == 200, dashboard.text
    assert "assignedTaskCount" in dashboard.json()["data"]


@pytest.mark.asyncio
async def test_reviewer_assignment_and_evidence_flow(client: AsyncClient):
    _, admin_headers = await _provision_enterprise_admin()
    reviewer = await _create_active_reviewer(client, admin_headers)

    create_assignment = await client.post(
        f"{BASE}/users/reviewers/{reviewer['user_id']}/assignments",
        headers=admin_headers,
        json={"title": "Quarterly compliance review", "taskKind": "project"},
    )
    assert create_assignment.status_code == 201, create_assignment.text
    assignment_id = create_assignment.json()["data"]["id"]

    list_assignments = await client.get(
        f"{BASE}/users/reviewers/{reviewer['user_id']}/assignments",
        headers=reviewer["headers"],
    )
    assert list_assignments.status_code == 200, list_assignments.text
    assert any(item["id"] == assignment_id for item in list_assignments.json()["data"])

    in_progress = await client.patch(
        f"{BASE}/reviewer/assignments/{assignment_id}",
        headers=reviewer["headers"],
        json={"status": "in_progress"},
    )
    assert in_progress.status_code == 200, in_progress.text
    assert in_progress.json()["data"]["status"] == "in_progress"

    completed = await client.patch(
        f"{BASE}/reviewer/assignments/{assignment_id}",
        headers=reviewer["headers"],
        json={"status": "completed"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["status"] == "completed"

    evidence_id = f"ev_{uuid.uuid4().hex[:8]}"
    evidence_assignment = await client.post(
        f"{BASE}/users/reviewers/{reviewer['user_id']}/assignments",
        headers=admin_headers,
        json={"title": "Evidence pack review", "taskKind": "evidence_review", "relatedId": evidence_id},
    )
    assert evidence_assignment.status_code == 201, evidence_assignment.text
    evidence_assignment_id = evidence_assignment.json()["data"]["id"]

    invalid_complete = await client.patch(
        f"{BASE}/reviewer/assignments/{evidence_assignment_id}",
        headers=reviewer["headers"],
        json={"status": "completed"},
    )
    assert invalid_complete.status_code == 400, invalid_complete.text

    recommend = await client.post(
        f"{BASE}/reviewer/evidence/{evidence_id}/recommend",
        headers=reviewer["headers"],
        json={"score": 91, "comment": "Evidence is sufficient.", "recommendation": "ACCEPT"},
    )
    assert recommend.status_code == 200, recommend.text

    projects = await client.get(f"{BASE}/reviewer/projects", headers=reviewer["headers"])
    assert projects.status_code == 200, projects.text
    matched = next(item for item in projects.json()["data"] if item["id"] == evidence_assignment_id)
    assert matched["status"] == "completed"


@pytest.mark.asyncio
async def test_non_reviewer_cannot_access_reviewer_dashboard(client: AsyncClient):
    admin_user, admin_headers = await _provision_enterprise_admin()
    assert admin_user["role"] == "enterprise"

    dashboard = await client.get(f"{BASE}/reviewer/dashboard", headers=admin_headers)
    assert dashboard.status_code == 403, dashboard.text


@pytest.mark.asyncio
async def test_reviewer_cannot_manage_other_reviewer_queue(client: AsyncClient):
    _, admin_headers = await _provision_enterprise_admin()
    reviewer_one = await _create_active_reviewer(client, admin_headers)
    reviewer_two = await _create_active_reviewer(client, admin_headers)

    denied = await client.post(
        f"{BASE}/users/reviewers/{reviewer_two['user_id']}/assignments",
        headers=reviewer_one["headers"],
        json={"title": "Forbidden queue write", "taskKind": "project"},
    )
    assert denied.status_code == 403, denied.text

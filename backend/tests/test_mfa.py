"""
MFA integration tests (requires MongoDB).
"""

import uuid

import pytest
import pytest_asyncio
import pyotp
from httpx import ASGITransport, AsyncClient

from app.core.database import close_db, connect_db
from app.main import app, create_indexes

BASE = "/api/v1"


@pytest_asyncio.fixture(autouse=True)
async def _db_lifespan():
    await connect_db()
    await create_indexes()
    yield
    await close_db()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _enterprise_payload(email: str) -> dict:
    return {
        "email": email,
        "password": "testpassword123",
        "firstName": "Test",
        "lastName": "Admin",
        "orgName": "Test Org",
        "orgType": "corporation",
        "industry": "technology",
        "companySize": "50-200",
        "adminTitle": "CTO",
        "acceptTos": True,
        "acceptPp": True,
        "acceptEsa": True,
        "acceptAhp": True,
    }


@pytest.mark.asyncio
async def test_enterprise_login_requires_mfa_setup_then_full_session(client):
    email = f"mfa_ent_{uuid.uuid4().hex[:8]}@test.com"
    reg = await client.post(f"{BASE}/auth/register/enterprise", json=_enterprise_payload(email))
    assert reg.status_code == 201, reg.text

    login = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "testpassword123", "role": "enterprise"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["status"] == "mfa_setup_required"
    assert "mfa_pending_token" in body
    pending = body["mfa_pending_token"]

    init = await client.post(
        f"{BASE}/auth/mfa/setup/init",
        headers={"Authorization": f"Bearer {pending}"},
    )
    assert init.status_code == 200, init.text
    secret = init.json()["secret_base32"]
    code = pyotp.TOTP(secret).now()

    confirm = await client.post(
        f"{BASE}/auth/mfa/setup/confirm",
        headers={"Authorization": f"Bearer {pending}"},
        json={"code": code},
    )
    assert confirm.status_code == 200, confirm.text
    cbody = confirm.json()
    assert len(cbody["recovery_codes"]) >= 1
    assert cbody["access_token"]
    assert cbody.get("refresh_token")

    me = await client.get(
        f"{BASE}/auth/me",
        headers={"Authorization": f"Bearer {cbody['access_token']}"},
    )
    assert me.status_code == 200
    mj = me.json()
    assert mj.get("mfaEnabled") is True or mj.get("mfa_enabled") is True


@pytest.mark.asyncio
async def test_enterprise_second_login_requires_totp(client):
    email = f"mfa_ent2_{uuid.uuid4().hex[:8]}@test.com"
    await client.post(f"{BASE}/auth/register/enterprise", json=_enterprise_payload(email))

    login1 = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "testpassword123", "role": "enterprise"},
    )
    pending = login1.json()["mfa_pending_token"]
    init = await client.post(
        f"{BASE}/auth/mfa/setup/init",
        headers={"Authorization": f"Bearer {pending}"},
    )
    secret = init.json()["secret_base32"]
    code = pyotp.TOTP(secret).now()
    await client.post(
        f"{BASE}/auth/mfa/setup/confirm",
        headers={"Authorization": f"Bearer {pending}"},
        json={"code": code},
    )

    login2 = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "testpassword123", "role": "enterprise"},
    )
    assert login2.json()["status"] == "mfa_required"
    pending2 = login2.json()["mfa_pending_token"]
    code2 = pyotp.TOTP(secret).now()
    verify = await client.post(
        f"{BASE}/auth/mfa/verify",
        headers={"Authorization": f"Bearer {pending2}"},
        json={"code": code2},
    )
    assert verify.status_code == 200
    assert verify.json()["access_token"]

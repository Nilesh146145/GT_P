from __future__ import annotations

import socket
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.database import close_db, connect_db, get_users_collection
from app.core.security import get_password_hash
from app.main import app, create_indexes
from app.services import oauth_service

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


def _contributor_payload(email: str) -> dict:
    return {
        "firstName": "Connie",
        "lastName": "Tributor",
        "email": email,
        "password": "Contributor123",
        "confirmPassword": "Contributor123",
        "contributorType": "general_workforce",
        "countryOfResidence": "India",
        "dateOfBirth": "1996-06-12",
        "timeZone": "Asia/Kolkata",
        "weeklyAvailabilityHours": 20,
        "departmentCategory": "Engineering",
        "primarySkills": ["Python"],
        "mentorGuideAcknowledged": True,
        "ndaSignatoryLegalName": "Connie Tributor",
        "phone": "+911111111111",
        "acceptTermsOfUse": True,
        "acceptCodeOfConduct": True,
        "acceptPrivacyPolicy": True,
        "acceptHarassmentPolicy": True,
        "acknowledgmentsAccepted": True,
        "notifyNewTasksOptIn": False,
    }


@pytest_asyncio.fixture(autouse=True)
async def _db_lifespan():
    if not _mongo_listening():
        pytest.skip("MongoDB not reachable on localhost:27017")
    await connect_db()
    await create_indexes()
    yield
    await close_db()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_registration_rejects_cross_role_email_reuse(client: AsyncClient):
    email = f"role_reg_{uuid.uuid4().hex[:8]}@test.com"
    reg_enterprise = await client.post(f"{BASE}/auth/register/enterprise", json=_enterprise_payload(email))
    assert reg_enterprise.status_code == 201, reg_enterprise.text

    reg_contributor = await client.post(f"{BASE}/auth/register/contributor", json=_contributor_payload(email))
    assert reg_contributor.status_code == 409, reg_contributor.text
    body = reg_contributor.json()
    assert body["detail"]["message"] == "This email is already registered as an enterprise account."


@pytest.mark.asyncio
async def test_login_rejects_role_mismatch(client: AsyncClient):
    email = f"role_login_{uuid.uuid4().hex[:8]}@test.com"
    reg_contributor = await client.post(f"{BASE}/auth/register/contributor", json=_contributor_payload(email))
    assert reg_contributor.status_code == 201, reg_contributor.text

    wrong_role = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "Contributor123", "role": "reviewer"},
    )
    assert wrong_role.status_code == 403, wrong_role.text
    assert wrong_role.json()["detail"]["message"] == "This email cannot be used for reviewer login."

    ok_role = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "Contributor123", "role": "contributor"},
    )
    assert ok_role.status_code == 200, ok_role.text
    assert ok_role.json()["user"]["role"] == "contributor"


@pytest.mark.asyncio
async def test_forgot_password_rejects_role_mismatch(client: AsyncClient):
    email = f"role_forgot_{uuid.uuid4().hex[:8]}@test.com"
    reg_enterprise = await client.post(f"{BASE}/auth/register/enterprise", json=_enterprise_payload(email))
    assert reg_enterprise.status_code == 201, reg_enterprise.text

    forgot_wrong = await client.post(
        f"{BASE}/auth/password/forgot",
        json={"email": email, "role": "reviewer"},
    )
    assert forgot_wrong.status_code == 409, forgot_wrong.text
    assert forgot_wrong.json()["detail"]["message"] == "Email already exists with a different role."

    forgot_ok = await client.post(
        f"{BASE}/auth/password/forgot",
        json={"email": email, "role": "enterprise"},
    )
    assert forgot_ok.status_code == 200, forgot_ok.text


@pytest.mark.asyncio
async def test_oauth_rejects_cross_role_email_reuse():
    email = f"role_oauth_{uuid.uuid4().hex[:8]}@test.com"
    users_col = get_users_collection()
    await users_col.insert_one(
        {
            "email": email,
            "hashed_password": get_password_hash("Password123"),
            "first_name": "Erin",
            "last_name": "Terprise",
            "full_name": "Erin Terprise",
            "role": "enterprise",
            "provider": "credentials",
            "mfa_enabled": True,
            "email_verified": False,
            "phone_verified": False,
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await oauth_service.find_or_create_oauth_user(
            email=email,
            first_name="OAuth",
            last_name="User",
            provider="google",
            expected_role="contributor",
        )
    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.detail["message"]
        == "This email is already registered as an enterprise account."
    )

import socket
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from app.core.database import close_db, connect_db, get_enterprises_collection, get_users_collection
from app.core.security import create_access_token, get_password_hash
from app.main import app, create_indexes

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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api_client:
        yield api_client


def _auth_headers(user_id: str, role: str) -> dict[str, str]:
    token = create_access_token({"sub": user_id, "role": role}, mfa_verified=True)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_contributor_profile_edit_and_picture_upload(client: AsyncClient):
    now = datetime.now(timezone.utc)
    email = f"contributor_{uuid.uuid4().hex[:8]}@test.com"
    contributor_doc = {
        "email": email,
        "hashed_password": get_password_hash("Password123"),
        "first_name": "Nilesh",
        "last_name": "User",
        "full_name": "Nilesh User",
        "phone": "9999999999",
        "role": "contributor",
        "provider": "credentials",
        "mfa_enabled": False,
        "requires_password_change": False,
        "is_first_login": False,
        "email_verified": False,
        "phone_verified": False,
        "contributor_profile": {
            "country_of_residence": "India",
            "time_zone": "Asia/Kolkata",
            "primary_skills": ["python"],
        },
        "created_at": now,
        "updated_at": now,
    }
    insert_result = await get_users_collection().insert_one(contributor_doc)
    user_id = str(insert_result.inserted_id)
    headers = _auth_headers(user_id, "contributor")

    update_payload = {
        "firstName": "Nilesh",
        "lastName": "Updated",
        "phoneNumber": "8888888888",
        "contributorProfile": {
            "timeZone": "Asia/Calcutta",
            "primarySkills": ["fastapi", "mongodb"],
            "secondarySkills": ["pytest"],
            "notifyNewTasksOptIn": True,
        },
    }
    update_res = await client.put(f"{BASE}/users/me/profile", headers=headers, json=update_payload)
    assert update_res.status_code == 200, update_res.text
    update_body = update_res.json()
    assert update_body["success"] is True
    assert update_body["data"]["lastName"] == "Updated"
    assert update_body["data"]["contributorProfile"]["time_zone"] == "Asia/Calcutta"
    assert update_body["data"]["contributorProfile"]["primary_skills"] == ["fastapi", "mongodb"]

    image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    upload_res = await client.post(
        f"{BASE}/users/me/profile-picture",
        headers=headers,
        files={"file": ("avatar.png", image_bytes, "image/png")},
    )
    assert upload_res.status_code == 200, upload_res.text
    assert upload_res.json()["data"]["profileImageUrl"].startswith("data:image/png;base64,")

    me_res = await client.get(f"{BASE}/auth/me", headers=headers)
    assert me_res.status_code == 200, me_res.text
    assert me_res.json()["profileImageUrl"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_enterprise_profile_update(client: AsyncClient):
    now = datetime.now(timezone.utc)
    enterprise_doc = {
        "org_name": "Old Org",
        "org_type": "corporation",
        "industry": "technology",
        "company_size": "11-50",
        "admin_title": "CTO",
        "created_at": now,
        "updated_at": now,
    }
    enterprise_result = await get_enterprises_collection().insert_one(enterprise_doc)
    enterprise_profile_id = str(enterprise_result.inserted_id)

    user_doc = {
        "email": f"enterprise_{uuid.uuid4().hex[:8]}@test.com",
        "hashed_password": get_password_hash("Password123"),
        "first_name": "Enter",
        "last_name": "Admin",
        "full_name": "Enter Admin",
        "role": "enterprise",
        "provider": "credentials",
        "phone": "9000000000",
        "enterprise_profile_id": enterprise_profile_id,
        "mfa_enabled": True,
        "requires_password_change": False,
        "is_first_login": False,
        "email_verified": False,
        "phone_verified": False,
        "created_at": now,
        "updated_at": now,
    }
    user_result = await get_users_collection().insert_one(user_doc)
    headers = _auth_headers(str(user_result.inserted_id), "enterprise")

    update_payload = {
        "firstName": "Enterprise",
        "enterpriseProfile": {
            "orgName": "New Org Name",
            "industry": "fintech",
            "adminTitle": "VP Engineering",
            "hqCity": "Pune",
        },
    }
    update_res = await client.put(f"{BASE}/users/me/profile", headers=headers, json=update_payload)
    assert update_res.status_code == 200, update_res.text
    body = update_res.json()
    assert body["data"]["firstName"] == "Enterprise"
    assert body["data"]["enterpriseProfile"]["orgName"] == "New Org Name"
    assert body["data"]["enterpriseProfile"]["hqCity"] == "Pune"

    enterprise_saved = await get_enterprises_collection().find_one({"_id": ObjectId(enterprise_profile_id)})
    assert enterprise_saved is not None
    assert enterprise_saved["org_name"] == "New Org Name"
    assert enterprise_saved["admin_title"] == "VP Engineering"

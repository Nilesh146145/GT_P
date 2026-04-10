import importlib
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
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
    os.environ["BILLING_API_ENABLED"] = "true" if enabled else "false"
    import app.core.config as config_module

    importlib.reload(config_module)
    import app.main as main_module

    return importlib.reload(main_module)


async def _insert_user(
    *,
    email: str,
    role: str,
    password: str = "BillingPass123",
    mfa_enabled: bool = False,
) -> dict:
    now = datetime.now(timezone.utc)
    document = {
        "email": email.lower(),
        "hashed_password": get_password_hash(password),
        "first_name": "Bill",
        "last_name": role.title(),
        "full_name": f"Bill {role.title()}",
        "role": role,
        "provider": "credentials",
        "mfa_enabled": mfa_enabled,
        "requires_password_change": False,
        "is_first_login": False,
        "email_verified": True,
        "phone_verified": False,
        "created_at": now,
        "updated_at": now,
    }
    result = await get_users_collection().insert_one(document)
    document["_id"] = result.inserted_id
    document["id"] = str(result.inserted_id)
    return document


def _auth_headers(user_id: str, role: str) -> dict[str, str]:
    token = create_access_token({"sub": user_id, "role": role}, mfa_verified=True)
    return {"Authorization": f"Bearer {token}"}


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


def test_billing_routes_not_registered_when_flag_disabled(main_module_disabled):
    paths = {route.path for route in main_module_disabled.app.routes}
    assert f"{BASE}/billing/invoices" not in paths
    assert f"{BASE}/billing/summary" not in paths


@pytest.mark.asyncio
async def test_billing_invoice_payment_refund_summary_and_receipt_flow(client: AsyncClient):
    contributor = await _insert_user(
        email=f"contrib_{uuid.uuid4().hex[:8]}@test.com",
        role="contributor",
        mfa_enabled=False,
    )
    admin = await _insert_user(
        email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
        role="admin",
        mfa_enabled=False,
    )

    contributor_headers = _auth_headers(contributor["id"], "contributor")
    admin_headers = _auth_headers(admin["id"], "admin")
    due_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    create_invoice = await client.post(
        f"{BASE}/billing/invoices",
        headers=contributor_headers,
        json={
            "payer_type": "contributor",
            "payer_id": contributor["id"],
            "currency": "USD",
            "due_at": due_at,
            "line_items": [
                {"description": "Audit prep", "quantity": 2, "unit_price": 100, "tax_rate": 10},
            ],
            "discount": 0,
            "notes": "Quarterly review billing",
        },
    )
    assert create_invoice.status_code == 201, create_invoice.text
    invoice_data = create_invoice.json()["data"]
    invoice_id = invoice_data["id"]
    assert invoice_data["total_amount"] == 220.0
    assert invoice_data["status"] == "pending"

    list_invoices = await client.get(
        f"{BASE}/billing/invoices",
        headers=contributor_headers,
        params={"page": 1, "page_size": 10, "sort_by": "date", "sort_dir": "desc"},
    )
    assert list_invoices.status_code == 200, list_invoices.text
    assert any(item["id"] == invoice_id for item in list_invoices.json()["data"])

    admin_get = await client.get(f"{BASE}/billing/invoices/{invoice_id}", headers=admin_headers)
    assert admin_get.status_code == 200, admin_get.text
    assert admin_get.json()["data"]["payer_id"] == contributor["id"]

    create_payment = await client.post(
        f"{BASE}/billing/payments",
        headers=admin_headers,
        json={
            "invoice_id": invoice_id,
            "amount": 100,
            "method": "wallet",
            "transaction_ref": "txn-001",
            "metadata": {"source": "test"},
        },
    )
    assert create_payment.status_code == 201, create_payment.text
    payment_data = create_payment.json()["data"]
    payment_id = payment_data["id"]
    assert payment_data["status"] == "completed"

    create_refund = await client.post(
        f"{BASE}/billing/refunds",
        headers=admin_headers,
        json={"payment_id": payment_id, "amount": 40, "reason": "Adjustment"},
    )
    assert create_refund.status_code == 201, create_refund.text
    refund_data = create_refund.json()["data"]
    assert refund_data["status"] == "processed"

    summary = await client.get(f"{BASE}/billing/summary", headers=contributor_headers)
    assert summary.status_code == 200, summary.text
    summary_data = summary.json()["data"]
    assert summary_data["total_invoiced"] == 220.0
    assert summary_data["total_paid"] == 60.0
    assert summary_data["total_pending"] == 160.0
    assert summary_data["total_overdue"] == 0.0
    assert summary_data["currency"] == "USD"

    receipt = await client.get(
        f"{BASE}/billing/invoices/{invoice_id}/receipt",
        headers=contributor_headers,
        params={"format": "pdf"},
    )
    assert receipt.status_code == 200, receipt.text
    assert receipt.headers["content-type"].startswith("application/pdf")
    assert receipt.content.startswith(b"%PDF")

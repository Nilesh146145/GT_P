"""
Billing API (FSD §10) — portfolio, snapshot, invoices, settings, admin raise/confirm.
"""

import uuid

import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.schemas.billing import BillingSettingsUpdate

BASE = "/api/v1"

_INDIA_BANK_BASE = {
    "billingContactEmail": "fin@test.com",
    "billingContactName": "Finance",
    "billingAddressLine1": "Line 1",
    "city": "Bengaluru",
    "stateProvince": "KA",
    "postalCode": "560001",
    "country": "IN",
    "gstOrVatNumber": "22AAAAA0000A1Z5",
    "preferredPaymentMethod": "bank_transfer_neft",
    "bankIfsc": "HDFC0001234",
}


def test_bs003_full_bank_account_9_to_18_digits_sets_last4():
    """BS-003 — numeric account 9–18 digits; persist derived last four only."""
    m = BillingSettingsUpdate.model_validate(
        {
            **_INDIA_BANK_BASE,
            "bankAccountNumber": "1234567890123456",
        }
    )
    assert m.bank_account_last4 == "3456"


def test_bs003_min_length_9_accepted():
    m = BillingSettingsUpdate.model_validate(
        {**_INDIA_BANK_BASE, "bankAccountNumber": "123456789"}
    )
    assert m.bank_account_last4 == "6789"


def test_bs003_max_length_18_accepted():
    m = BillingSettingsUpdate.model_validate(
        {**_INDIA_BANK_BASE, "bankAccountNumber": "1" * 18}
    )
    assert m.bank_account_last4 == "1111"


def test_bs003_rejects_non_numeric():
    with pytest.raises(ValidationError, match="Invalid bank account number format"):
        BillingSettingsUpdate.model_validate(
            {**_INDIA_BANK_BASE, "bankAccountNumber": "12345678A1234567"}
        )


def test_bs003_rejects_too_short():
    with pytest.raises(ValidationError, match="Invalid bank account number format"):
        BillingSettingsUpdate.model_validate(
            {**_INDIA_BANK_BASE, "bankAccountNumber": "12345678"}
        )


def test_bs003_rejects_too_long():
    with pytest.raises(ValidationError, match="Invalid bank account number format"):
        BillingSettingsUpdate.model_validate(
            {**_INDIA_BANK_BASE, "bankAccountNumber": "1" * 19}
        )


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
async def enterprise_headers(client):
    email = f"bill_ent_{uuid.uuid4().hex[:10]}@test.com"
    r = await client.post(f"{BASE}/auth/register", json=_register_json(email))
    assert r.status_code == 201, r.text
    lr = await client.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    assert lr.status_code == 200, lr.text
    return {"Authorization": f"Bearer {lr.json()['access_token']}"}


@pytest_asyncio.fixture
async def admin_headers(client):
    email = f"bill_adm_{uuid.uuid4().hex[:10]}@test.com"
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
    return {"Authorization": f"Bearer {lr.json()['access_token']}"}


@pytest.mark.asyncio
async def test_billing_portfolio_snapshot_and_raise_confirm(
    client,
    enterprise_headers,
    admin_headers,
):
    """Create project, portfolio + snapshot, admin raises M1 and confirms payment."""
    body = {
        "name": "Alpha",
        "clientName": "Client A",
        "currency": "USD",
        "contractedAmount": 100000,
        "commercialReviewComplete": True,
        "uatSignoffComplete": False,
    }
    cr = await client.post(
        f"{BASE}/billing/projects",
        json=body,
        headers=enterprise_headers,
    )
    assert cr.status_code == 201, cr.text
    pr = await client.get(f"{BASE}/billing/portfolio", headers=enterprise_headers)
    assert pr.status_code == 200, pr.text
    payload = pr.json()
    assert payload["success"] is True
    row = payload["data"]["projects"][0]
    assert row["contracted"]["value"] == 100000.0
    assert row["contracted"]["pendingReview"] is False
    assert row["m1"]["amount"] == 30000.0
    m1_id = row["m1"]["invoiceId"]
    assert m1_id

    sn = await client.get(f"{BASE}/billing/snapshot", headers=enterprise_headers)
    assert sn.status_code == 200
    snap = sn.json()["data"]
    assert snap["totalContracted"] == 100000.0

    inv = await client.get(f"{BASE}/billing/invoices", headers=enterprise_headers)
    assert inv.status_code == 200
    items = inv.json()["data"]
    assert len(items) == 3
    assert items[0]["status"] in ("PENDING", "AWAITING_SIGNOFF", "OVERDUE", "DUE")

    ar = await client.post(
        f"{BASE}/billing/admin/invoices/{m1_id}/raise",
        headers=admin_headers,
    )
    assert ar.status_code == 200, ar.text
    assert ar.json()["data"]["status"] == "DUE"

    cp = await client.post(
        f"{BASE}/billing/admin/invoices/{m1_id}/confirm-payment",
        headers=admin_headers,
    )
    assert cp.status_code == 200, cp.text
    assert cp.json()["data"]["status"] == "PAID"

    pr2 = await client.get(f"{BASE}/billing/portfolio", headers=enterprise_headers)
    row2 = pr2.json()["data"]["projects"][0]
    assert row2["m1"]["status"] == "PAID"
    assert row2["totalPaid"] == 30000.0


@pytest.mark.asyncio
async def test_billing_settings_patch_india_gst(client, enterprise_headers):
    """GSTIN required for India; valid 15-char GST passes."""
    gst = "22AAAAA0000A1Z5"
    patch = {
        "billingContactEmail": "fin@test.com",
        "billingContactName": "Finance",
        "billingAddressLine1": "Line 1",
        "billingAddressLine2": "",
        "city": "Bengaluru",
        "stateProvince": "KA",
        "postalCode": "560001",
        "country": "IN",
        "gstOrVatNumber": gst,
        "preferredPaymentMethod": "bank_transfer_neft",
        "bankAccountLast4": "1234",
        "bankIfsc": "HDFC0001234",
    }
    r = await client.patch(
        f"{BASE}/billing/settings",
        json=patch,
        headers=enterprise_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["gstOrVatNumber"] == gst


@pytest.mark.asyncio
async def test_billing_settings_india_rejects_bad_gst(client, enterprise_headers):
    r = await client.patch(
        f"{BASE}/billing/settings",
        json={
            "billingContactEmail": "fin@test.com",
            "billingContactName": "Finance",
            "billingAddressLine1": "Line 1",
            "city": "Bengaluru",
            "stateProvince": "KA",
            "postalCode": "560001",
            "country": "IN",
            "gstOrVatNumber": "BAD",
            "preferredPaymentMethod": "wallet",
        },
        headers=enterprise_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_billing_pending_review_contracted(client, enterprise_headers):
    """BILL-003: pending review when Stage 2 commercial not complete."""
    body = {
        "name": "Beta",
        "clientName": "Client B",
        "currency": "INR",
        "commercialReviewComplete": False,
    }
    await client.post(
        f"{BASE}/billing/projects",
        json=body,
        headers=enterprise_headers,
    )
    pr = await client.get(f"{BASE}/billing/portfolio", headers=enterprise_headers)
    rows = pr.json()["data"]["projects"]
    beta = next(r for r in rows if r["name"] == "Beta")
    assert beta["contracted"]["pendingReview"] is True
    assert beta["contracted"]["value"] is None

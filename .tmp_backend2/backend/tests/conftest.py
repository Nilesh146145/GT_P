"""
Shared pytest fixtures.

``httpx.ASGITransport`` does not run FastAPI lifespan by default, so we open the
MongoDB client explicitly before integration tests.
"""

import os
from typing import Optional

# Fail fast when MongoDB is unavailable (avoid long hangs in CI / local without mongod)
_mongo_url = os.environ.get("MONGODB_URL", "mongodb://127.0.0.1:27017")
if "serverSelectionTimeoutMS" not in _mongo_url:
    _sep = "&" if "?" in _mongo_url else "?"
    # Short timeout so tests skip quickly when MongoDB is not running locally.
    os.environ["MONGODB_URL"] = f"{_mongo_url}{_sep}serverSelectionTimeoutMS=1000"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import close_db, connect_db, get_database
from app.main import app

_mongo_reachable: Optional[bool] = None
_mongo_fail_reason: Optional[str] = None


@pytest_asyncio.fixture
async def client():
    """ASGI client; skips tests if MongoDB is not reachable (local dev without mongod)."""
    global _mongo_reachable, _mongo_fail_reason
    if _mongo_reachable is False:
        pytest.skip(_mongo_fail_reason or "MongoDB not reachable")
    await connect_db()
    if _mongo_reachable is None:
        try:
            await get_database().command("ping")
            _mongo_reachable = True
        except Exception as exc:
            _mongo_reachable = False
            _mongo_fail_reason = (
                "MongoDB not reachable (start MongoDB or set MONGODB_URL): "
                f"{exc}"
            )
            await close_db()
            pytest.skip(_mongo_fail_reason)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c
    finally:
        await close_db()

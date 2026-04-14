from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseNotAvailable(RuntimeError):
    """Mongo client is None (connection failed at startup — API is in degraded mode)."""


from app.models.reviewer import (
    REVIEWER_ASSIGNMENTS_COLLECTION,
    REVIEWER_EVIDENCE_COLLECTION,
    REVIEWER_PROJECTS_COLLECTION,
    REVIEWER_RECOMMENDATIONS_COLLECTION,
)

client: AsyncIOMotorClient = None


def _mongo_url_for_log(url: str) -> str:
    """Avoid printing credentials from connection string."""
    if "@" in url:
        return f"...@{url.split('@', 1)[-1]}"
    return url


async def connect_db() -> None:
    """Create Motor client; on failure leave client None so HTTP can still start (e.g. Render)."""
    global client
    try:
        client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
            connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        )
        await client[settings.DATABASE_NAME].command("ping")
        print(f"Connected to MongoDB: {_mongo_url_for_log(settings.MONGODB_URL)}")
    except Exception as e:
        logger.warning(
            "MongoDB unavailable — API starts in degraded mode. %s (%s: %s)",
            _mongo_url_for_log(settings.MONGODB_URL),
            type(e).__name__,
            e,
        )
        if "localhost" in settings.MONGODB_URL or "127.0.0.1" in settings.MONGODB_URL:
            logger.warning(
                "MONGODB_URL still points at this machine (%s). For MongoDB Atlas, "
                "replace it in backend/.env with the mongodb+srv://… string from Atlas "
                "(Database → Connect → Drivers), allow your IP under Network Access, then restart.",
                _mongo_url_for_log(settings.MONGODB_URL),
            )
        client = None


async def close_db():
    global client
    if client:
        client.close()
        print("MongoDB connection closed.")


def is_db_connected() -> bool:
    return client is not None


def get_database():
    if client is None:
        raise DatabaseNotAvailable(
            "Database not initialized — set MONGODB_URL and ensure MongoDB is reachable, then restart the server."
        )
    return client[settings.DATABASE_NAME]


# Alias used by auth router and services
def get_db():
    return get_database()


# Collection accessors
def get_users_collection():
    return get_database()["users"]


def get_wizards_collection():
    return get_database()["wizards"]


def get_sows_collection():
    return get_database()["sows"]


def get_approvals_collection():
    return get_database()["approvals"]


# Manual SOW intake (upload flow) — separate from wizard `sows` collection
def get_manual_sows_collection():
    return get_database()["manual_sows"]


def get_manual_sow_files_collection():
    return get_database()["manual_sow_files"]


def get_manual_sow_extraction_items_collection():
    return get_database()["manual_sow_extraction_items"]


def get_manual_sow_gap_items_collection():
    return get_database()["manual_sow_gap_items"]


def get_manual_sow_approval_messages_collection():
    return get_database()["manual_sow_approval_messages"]


def get_manual_sow_audit_log_collection():
    return get_database()["manual_sow_audit_log"]


def get_enterprises_collection():
    return get_database()["enterprises"]


def get_otp_collection():
    return get_database()["otp_codes"]


def get_password_resets_collection():
    return get_database()["password_resets"]


def get_sessions_collection():
    return get_database()["sessions"]


def get_totp_credentials_collection():
    return get_database()["user_totp_credentials"]


def get_mfa_recovery_codes_collection():
    return get_database()["user_mfa_recovery_codes"]


def get_mfa_setup_pending_collection():
    return get_database()["mfa_setup_pending"]


def get_mfa_audit_collection():
    return get_database()["mfa_audit_log"]


def get_reviewer_assignments_collection():
    return get_database()[REVIEWER_ASSIGNMENTS_COLLECTION]


def get_reviewer_evidence_collection():
    return get_database()[REVIEWER_EVIDENCE_COLLECTION]


def get_reviewer_recommendations_collection():
    return get_database()[REVIEWER_RECOMMENDATIONS_COLLECTION]


def get_reviewer_projects_collection():
    return get_database()[REVIEWER_PROJECTS_COLLECTION]


def get_decomposition_plans_collection():
    return get_database()["decomposition_plans"]

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    print(f"Connected to MongoDB: {settings.MONGODB_URL}")


async def close_db():
    global client
    if client:
        client.close()
        print("MongoDB connection closed.")


def get_database():
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

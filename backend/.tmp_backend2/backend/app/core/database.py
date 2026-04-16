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


def get_enterprises_collection():
    return get_database()["enterprises"]


def get_otp_collection():
    return get_database()["otp_codes"]


def get_password_resets_collection():
    return get_database()["password_resets"]


def get_sessions_collection():
    return get_database()["sessions"]


def get_reviewer_assignments_collection():
    """Work queue items assigned to platform reviewers (dashboard / projects)."""
    return get_database()["reviewer_assignments"]


def get_evidence_recommendations_collection():
    """Stored ACCEPT/REWORK decisions from reviewers (evidence pack reviews)."""
    return get_database()["evidence_recommendations"]


def get_billing_projects_collection():
    """Enterprise billing portfolio — one row per billable project (FSD §10)."""
    return get_database()["billing_projects"]


def get_billing_invoices_collection():
    """Milestone invoices (M1/M2/M3) per project."""
    return get_database()["billing_invoices"]


def get_billing_counters_collection():
    """Monotonic invoice number sequences (GT-YYYY-NNN)."""
    return get_database()["billing_counters"]

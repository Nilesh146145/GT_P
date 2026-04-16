"""
Session collection accessor — kept separate to avoid circular imports.
Sessions are stored in the `sessions` MongoDB collection.
"""
from __future__ import annotations

from app.core.database import get_database


def get_sessions_collection():
    return get_database()["sessions"]

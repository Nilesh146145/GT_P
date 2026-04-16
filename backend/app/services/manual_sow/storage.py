"""Local filesystem storage for manual SOW uploads."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.core.config import settings


def ensure_storage_dir() -> Path:
    base = Path(settings.MANUAL_SOW_STORAGE_PATH)
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_upload(sow_public_id: str, original_name: str, content: bytes) -> tuple[str, int]:
    """Returns (relative_storage_key, size_bytes)."""
    ext = Path(original_name).suffix.lower() or ".bin"
    key = f"{sow_public_id}/{uuid.uuid4().hex}{ext}"
    base = ensure_storage_dir()
    dest = base / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return key, len(content)


def read_file(storage_key: str) -> bytes:
    base = ensure_storage_dir()
    path = base / storage_key
    if not path.is_file():
        raise FileNotFoundError(storage_key)
    return path.read_bytes()

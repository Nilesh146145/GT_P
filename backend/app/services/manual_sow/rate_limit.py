"""Simple in-process rate limits for Manual SOW routes (spec §19)."""

from __future__ import annotations

import time
from collections import defaultdict

from app.core.config import settings


class SlidingWindowLimiter:
    """Tracks timestamps per key; not shared across workers."""

    def __init__(self) -> None:
        self._events: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, max_events: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        arr = self._events[key]
        arr[:] = [t for t in arr if t > cutoff]
        if len(arr) >= max_events:
            return False
        arr.append(now)
        return True


_upload_limiter = SlidingWindowLimiter()
_api_limiter = SlidingWindowLimiter()


def user_rate_key(user_id: str, bucket: str) -> str:
    return f"{bucket}:{user_id}"


def check_upload_rate(user_id: str) -> bool:
    return _upload_limiter.check(
        user_rate_key(user_id, "upload"),
        settings.MANUAL_SOW_RATE_UPLOAD_PER_MINUTE,
        60,
    )


def check_api_rate(user_id: str) -> bool:
    return _api_limiter.check(
        user_rate_key(user_id, "api"),
        settings.MANUAL_SOW_RATE_API_PER_MINUTE,
        60,
    )

"""
MFA endpoint rate limiting. Uses Redis when REDIS_URL is set; otherwise in-process (single worker friendly).
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from fastapi import HTTPException, status

from app.core.config import settings

_redis_client = None
_redis_unavailable = False
_memory_hits: dict[str, list[float]] = defaultdict(list)
_memory_lock = asyncio.Lock()


def _get_redis():
    global _redis_client, _redis_unavailable
    if _redis_unavailable or not settings.REDIS_URL:
        return None
    if _redis_client is None:
        try:
            import redis.asyncio as redis  # type: ignore

            _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            _redis_unavailable = True
            return None
    return _redis_client


async def check_rate_limit(
    *,
    scope: str,
    bucket: str,
    max_events: int,
    window_seconds: int,
) -> None:
    """
    Raise HTTP 429 if more than max_events occurred for (scope, bucket) in window_seconds.
    """
    key = f"{scope}:{bucket}"
    r = _get_redis()
    if r is not None:
        try:
            n = await r.incr(key)
            if n == 1:
                await r.expire(key, window_seconds)
            if int(n) > max_events:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"code": "RATE_LIMITED", "message": "Too many attempts. Try again later."},
                    headers={"Retry-After": str(window_seconds)},
                )
            return
        except HTTPException:
            raise
        except Exception:
            pass

    now = time.monotonic()
    cutoff = now - window_seconds
    async with _memory_lock:
        hits = _memory_hits[key]
        hits[:] = [t for t in hits if t > cutoff]
        if len(hits) >= max_events:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "RATE_LIMITED", "message": "Too many attempts. Try again later."},
                headers={"Retry-After": str(window_seconds)},
            )
        hits.append(now)

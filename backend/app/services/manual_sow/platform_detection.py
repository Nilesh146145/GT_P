"""
Infer Manual SOW ``platformType`` from raw document text (extraction pipeline).
"""

from __future__ import annotations

import re
from typing import Set

from app.schemas.manual_sow.manual_sow_platform_type import ManualSowPlatformType

P = ManualSowPlatformType
MOBILE_ONLY = frozenset({P.MOBILE_IOS, P.MOBILE_ANDROID, P.MOBILE_HYBRID})


def _collect_platform_hits(low: str) -> Set[ManualSowPlatformType]:
    """Return all platform categories implied by substring rules (case-insensitive)."""
    hits: Set[ManualSowPlatformType] = set()

    if any(
        p in low
        for p in (
            "full stack",
            "full-stack",
            "fullstack",
            "end-to-end",
            "end to end",
            "end-to-end system",
        )
    ):
        hits.add(P.FULL_STACK)

    if any(
        p in low
        for p in ("data platform", "etl pipeline", "analytics platform", "data pipeline")
    ):
        hits.add(P.DATA_PLATFORM)
    elif "pipeline" in low and any(x in low for x in ("data", "etl", "analytics", "snowflake", "databricks")):
        hits.add(P.DATA_PLATFORM)
    elif "analytics" in low and any(x in low for x in ("platform", "warehouse", "bi tool", "power bi", "tableau")):
        hits.add(P.DATA_PLATFORM)

    if any(p in low for p in ("api only", "backend only", "headless api", "microservices only")):
        hits.add(P.API_BACKEND_ONLY)

    if any(p in low for p in ("desktop", "windows app", "macos app", "electron app", "native desktop")):
        hits.add(P.DESKTOP)

    if any(p in low for p in ("react native", "react-native", "flutter", "mobile app", "mobile application")):
        hits.add(P.MOBILE_HYBRID)

    if re.search(r"\bios\b", low) or "iphone" in low or "ipad" in low:
        hits.add(P.MOBILE_IOS)

    if "android" in low:
        hits.add(P.MOBILE_ANDROID)

    if any(
        p in low
        for p in (
            "web app",
            "web application",
            "website",
            "browser-based",
            "browser based",
            "single-page app",
            "web portal",
            "admin portal",
            "customer portal",
        )
    ):
        hits.add(P.WEB_APPLICATION)
    elif " spa" in low or low.startswith("spa ") or "progressive web" in low or "pwa" in low:
        hits.add(P.WEB_APPLICATION)

    return hits


def infer_platform_type_from_text(text: str) -> str:
    """
    Choose a single ManualSowPlatformType from document text.

    Multiple **mobile-only** signals (iOS + Android + hybrid keywords) → ``MOBILE_HYBRID``,
    not ``FULL_STACK``. ``FULL_STACK`` is reserved for **compound** delivery (e.g. mobile + web,
    or web + data platform) where more than one *non-mobile* category applies or mobile is
    combined with web/full-stack hints.
    """
    low = (text or "").lower()
    if not low.strip():
        return P.OTHER.value

    hits = _collect_platform_hits(low)
    if not hits:
        return P.OTHER.value

    mobile_hits = hits & MOBILE_ONLY
    non_mobile = hits - MOBILE_ONLY

    # Only mobile facets → one cross-platform or native choice (never collapse to FULL_STACK here).
    if mobile_hits and not non_mobile:
        if P.MOBILE_HYBRID in mobile_hits:
            return P.MOBILE_HYBRID.value
        if P.MOBILE_IOS in mobile_hits and P.MOBILE_ANDROID in mobile_hits:
            return P.MOBILE_HYBRID.value
        if len(mobile_hits) >= 2:
            return P.MOBILE_HYBRID.value
        return next(iter(mobile_hits)).value

    if len(hits) == 1:
        return next(iter(hits)).value

    # Mobile combined with web, data, API-only emphasis, desktop, etc. → full product surface.
    if mobile_hits and non_mobile:
        return P.FULL_STACK.value

    if P.FULL_STACK in hits:
        return P.FULL_STACK.value
    return P.FULL_STACK.value

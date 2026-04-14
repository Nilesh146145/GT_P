"""
Platform classification for Manual SOW delivery scope (document-derived + API).

Distinct from wizard ``PlatformType`` in ``app.schemas.common`` (human-readable labels).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class ManualSowPlatformType(str, Enum):
    """Stored in ``commercial_details.deliveryScope.platformType`` (camelCase JSON)."""

    WEB_APPLICATION = "WEB_APPLICATION"
    MOBILE_IOS = "MOBILE_IOS"
    MOBILE_ANDROID = "MOBILE_ANDROID"
    MOBILE_HYBRID = "MOBILE_HYBRID"
    DESKTOP = "DESKTOP"
    API_BACKEND_ONLY = "API_BACKEND_ONLY"
    DATA_PLATFORM = "DATA_PLATFORM"
    FULL_STACK = "FULL_STACK"
    OTHER = "OTHER"


_ALLOWED_PLATFORM_VALUES = frozenset(e.value for e in ManualSowPlatformType)


def normalize_manual_sow_platform_type(raw: Any) -> Optional[str]:
    """
    Map UI / human labels to a stored enum value.

    PATCH and extraction prefill must accept values like ``web application``; otherwise
    ``validate_section`` fails, GET prefill treats delivery scope as invalid, and
    ``merge_delivery_scope_with_repair`` overwrites ``platformType`` with the document
    seed (often MOBILE_HYBRID) — making user edits appear to "revert".
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s in _ALLOWED_PLATFORM_VALUES:
        return s
    cand = s.upper().replace("-", "_").replace(" ", "_")
    while "__" in cand:
        cand = cand.replace("__", "_")
    if cand in _ALLOWED_PLATFORM_VALUES:
        return cand
    # Labels that do not underscore-match the enum member name (common UI / speech variants).
    aliases = {
        "WEBAPP": ManualSowPlatformType.WEB_APPLICATION.value,
        "WEBSITE": ManualSowPlatformType.WEB_APPLICATION.value,
        "SPA": ManualSowPlatformType.WEB_APPLICATION.value,
        "PWA": ManualSowPlatformType.WEB_APPLICATION.value,
        "FULLSTACK": ManualSowPlatformType.FULL_STACK.value,
        "IOS": ManualSowPlatformType.MOBILE_IOS.value,
        "IPHONE": ManualSowPlatformType.MOBILE_IOS.value,
        "ANDROID": ManualSowPlatformType.MOBILE_ANDROID.value,
        "HYBRID": ManualSowPlatformType.MOBILE_HYBRID.value,
        "CROSS_PLATFORM": ManualSowPlatformType.MOBILE_HYBRID.value,
        "CROSSPLATFORM": ManualSowPlatformType.MOBILE_HYBRID.value,
        "REACT_NATIVE": ManualSowPlatformType.MOBILE_HYBRID.value,
        "REACTNATIVE": ManualSowPlatformType.MOBILE_HYBRID.value,
        "FLUTTER": ManualSowPlatformType.MOBILE_HYBRID.value,
        "BACKEND_ONLY": ManualSowPlatformType.API_BACKEND_ONLY.value,
        "HEADLESS": ManualSowPlatformType.API_BACKEND_ONLY.value,
        "HEADLESS_API": ManualSowPlatformType.API_BACKEND_ONLY.value,
        "MICROSERVICES": ManualSowPlatformType.API_BACKEND_ONLY.value,
        "API_BACKEND": ManualSowPlatformType.API_BACKEND_ONLY.value,
        "DATAPLATFORM": ManualSowPlatformType.DATA_PLATFORM.value,
        "ANALYTICS_PLATFORM": ManualSowPlatformType.DATA_PLATFORM.value,
        "ETL": ManualSowPlatformType.DATA_PLATFORM.value,
        "DESKTOP_APP": ManualSowPlatformType.DESKTOP.value,
        "NATIVE_DESKTOP": ManualSowPlatformType.DESKTOP.value,
    }
    return aliases.get(cand)

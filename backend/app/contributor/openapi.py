"""Attach HTTPBearer to OpenAPI for ``/api/contributor/*`` operations."""

from __future__ import annotations

from typing import Any

_HTTP_OPS = frozenset({"get", "post", "put", "patch", "delete", "options", "head"})


def patch_contributor_paths_security(openapi_schema: dict[str, Any]) -> None:
    components = openapi_schema.setdefault("components", {})
    schemes = components.setdefault("securitySchemes", {})
    if "HTTPBearer" not in schemes:
        schemes["HTTPBearer"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Use access_token from POST /api/v1/auth/login (or OAuth). "
                "Paste JWT only — Swagger adds Bearer. "
                "MFA: complete /api/v1/auth/mfa/* flow if required. "
                "With AUTH_ALLOW_HEADER_FALLBACK=true, X-Contributor-Id works without JWT (dev only)."
            ),
        }

    paths = openapi_schema.get("paths") or {}
    for path, path_item in paths.items():
        if not path.startswith("/api/contributor"):
            continue
        for method, op in path_item.items():
            if method not in _HTTP_OPS or not isinstance(op, dict):
                continue
            op["security"] = [{"HTTPBearer": []}]

"""
Minimal app: contributor routes + shared auth stack (MongoDB, /api/v1/auth, MFA, OAuth).

Run from ``backend``:

    uvicorn app.contributor_only:app --reload --port 8080

Use the same ``POST /api/v1/auth/login`` (or OAuth) as the full app; then call ``GET /api/contributor/session``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.contributor import router as contributor_router
from app.core.database import close_db, connect_db
from app.routers import auth, mfa, oauth

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await connect_db()
    try:
        from app.contributor import demo_bootstrap

        demo_bootstrap.install_temp_api_db_layout()
        demo_bootstrap.apply_all_temp_demo_seeds()
    except Exception:
        _log.exception("Contributor demo bootstrap failed; continuing")
    yield
    await close_db()


app = FastAPI(
    title="Glimmora Contributor (subset)",
    version="1.0.0",
    lifespan=lifespan,
    description="Contributor APIs + platform auth. Full app: ``uvicorn app.main:app``.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(oauth.router, prefix=API_PREFIX)
app.include_router(mfa.router, prefix=API_PREFIX)
app.include_router(contributor_router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    from app.contributor.openapi import patch_contributor_paths_security

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    patch_contributor_paths_security(openapi_schema)
    schemes = openapi_schema.get("components", {}).get("securitySchemes") or {}
    for scheme in schemes.values():
        if scheme.get("type") == "http" and scheme.get("scheme") == "bearer":
            scheme["description"] = (
                "Paste ONLY the JWT. Do NOT type Bearer — Swagger adds it automatically."
            )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "contributor-only"}

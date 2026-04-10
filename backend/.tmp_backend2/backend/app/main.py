"""
GlimmoraTeam — AI SOW Generator API
FastAPI + MongoDB backend for the 10-step SOW Wizard.
"""

import html
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import connect_db, close_db
from app.routers import auth, wizard, sow, approvals, users, reviewer, billing

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# LIFESPAN
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    try:
        await create_indexes()
    except Exception as exc:
        # Without this, uvicorn never binds and /docs is unreachable if MongoDB is down.
        logger.warning("MongoDB index setup failed (is mongod running?): %s", exc)
    yield
    await close_db()


async def create_indexes():
    """Create MongoDB indexes for performance."""
    from app.core.database import get_database
    db = get_database()

    # Users
    await db["users"].create_index("email", unique=True)

    # Wizards
    await db["wizards"].create_index("created_by_user_id")
    await db["wizards"].create_index("enterprise_id")
    await db["wizards"].create_index("status")

    # SOWs
    await db["sows"].create_index("wizard_id")
    await db["sows"].create_index("created_by_user_id")
    await db["sows"].create_index("status")
    await db["sows"].create_index("enterprise_id")

    # OTP codes (TTL — auto-expire)
    await db["otp_codes"].create_index([("type", 1), ("target", 1)])
    await db["otp_codes"].create_index("expires_at", expireAfterSeconds=0)

    # Password reset tokens (TTL — expire 1 hour after creation)
    await db["password_resets"].create_index("token", unique=True)
    await db["password_resets"].create_index("expires_at", expireAfterSeconds=0)

    # Sessions — active refresh token sessions
    await db["sessions"].create_index("user_id")
    await db["sessions"].create_index("refresh_token_hash", unique=True)
    await db["sessions"].create_index("expires_at", expireAfterSeconds=0)  # TTL auto-expire

    # Reviewer assignments + evidence recommendations
    await db["reviewer_assignments"].create_index("reviewer_user_id")
    await db["reviewer_assignments"].create_index([("reviewer_user_id", 1), ("status", 1)])
    await db["evidence_recommendations"].create_index("reviewer_user_id")
    await db["evidence_recommendations"].create_index([("evidence_id", 1), ("reviewer_user_id", 1)])

    # Billing (FSD §10)
    await db["billing_projects"].create_index("enterprise_id")
    await db["billing_projects"].create_index([("enterprise_id", 1), ("name", 1)])
    await db["billing_invoices"].create_index("enterprise_id")
    await db["billing_invoices"].create_index("project_id")
    await db["billing_invoices"].create_index([("enterprise_id", 1), ("project_id", 1)])
    # Unique invoice numbers when set; omit ``sparse`` — MongoDB forbids sparse + partialFilterExpression together.
    await db["billing_invoices"].create_index(
        "invoice_number",
        unique=True,
        partialFilterExpression={"invoice_number": {"$type": "string"}},
    )

    print("MongoDB indexes created.")


# ──────────────────────────────────────────────
# APP INSTANCE
# ──────────────────────────────────────────────

_openapi_tags = [
    {"name": "Health", "description": "Liveness and database connectivity."},
        {
            "name": "Authentication",
            "description": (
                "Public: ``POST /auth/login``, ``/auth/validate``, ``/auth/register/enterprise``, "
                "``/auth/register/contributor``, ``/auth/refresh``, ``/auth/logout``, ``/auth/password/forgot``. "
                "Protected: ``/auth/logout-all``, ``/auth/me``, ``/auth/session``, ``/auth/sessions``, revoke session, "
                "``/auth/password/change``. "
                "MFA: ``/auth/mfa/*`` (see MFA tag)."
            ),
        },
        {
            "name": "MFA",
            "description": (
                "Six operations: ``setup/init``, ``setup/confirm``, ``verify``, ``recovery``, ``disable``, ``status``. "
                "Extra helpers (cancel setup, rotate recovery codes) exist but are omitted from this document."
            ),
        },
    {"name": "SOW Wizard", "description": "10-step wizard CRUD and SOW generation."},
    {"name": "AI Draft Review", "description": "List and review generated SOWs, hallucination analysis, actions."},
    {
        "name": "Approval Pipeline",
        "description": "Multi-stage approval pipeline.",
    },
    {
        "name": "Users & Enterprise",
        "description": "User search and admin reviewer provisioning.",
    },
    {"name": "Billing", "description": "Enterprise billing — portfolio, invoices, settings (FSD §10)."},
]
if settings.REVIEWER_API_ENABLED:
    _openapi_tags.append(
        {"name": "Reviewer", "description": "Reviewer dashboard and evidence (requires MFA)."},
    )

app = FastAPI(
    title="GlimmoraTeam API",
    description="",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    openapi_tags=_openapi_tags,
)
# OpenAPI version is not a FastAPI() kwarg (see FastAPI docs); set on the instance for ``custom_openapi``.
app.openapi_version = "3.0.2"

# ── Swagger UI (vendored) — optional: if files are missing, ``/docs`` redirects to ``/redoc``.
_STATIC_SWAGGER_DIR = Path(__file__).resolve().parent / "static" / "swagger-ui"
# Swagger UI 5: BaseLayout preset lives on ``SwaggerUIBundle.SwaggerUIStandalonePreset`` (single bundle).
_STATIC_SWAGGER_REQUIRED = (
    "swagger-ui-bundle.js",
    "swagger-ui.css",
)
_SWAGGER_ASSETS_READY = _STATIC_SWAGGER_DIR.is_dir() and all(
    (_STATIC_SWAGGER_DIR / f).is_file() for f in _STATIC_SWAGGER_REQUIRED
)
if _SWAGGER_ASSETS_READY:
    app.mount(
        "/swagger-assets",
        StaticFiles(directory=_STATIC_SWAGGER_DIR),
        name="swagger-assets",
    )
else:
    logger.warning(
        "Swagger UI files missing under %s — open /redoc instead. See app/static/swagger-ui/README.txt",
        _STATIC_SWAGGER_DIR,
    )

# ReDoc single bundle (vendored) — reliable in Safari when Swagger UI fails.
_REDOC_STATIC_DIR = Path(__file__).resolve().parent / "static" / "redoc"
_REDOC_JS = _REDOC_STATIC_DIR / "redoc.standalone.js"
_REDOC_READY = _REDOC_JS.is_file()
if _REDOC_READY:
    app.mount(
        "/redoc-assets",
        StaticFiles(directory=_REDOC_STATIC_DIR),
        name="redoc-assets",
    )
else:
    logger.warning(
        "ReDoc bundle missing at %s — download per app/static/redoc/README.txt",
        _REDOC_JS,
    )


def _openapi_spec_url(request: Request) -> str:
    """Public URL for ``/openapi.json`` (works behind ``X-Forwarded-Prefix``)."""
    prefix = (request.headers.get("x-forwarded-prefix") or "").strip().rstrip("/")
    base = str(request.base_url).rstrip("/")
    return f"{base}{prefix}/openapi.json"


def _redoc_html_page(*, openapi_url: str) -> str:
    spec_attr = html.escape(openapi_url, quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>API reference (ReDoc)</title>
</head>
<body>
  <redoc spec-url="{spec_attr}"></redoc>
  <script src="/redoc-assets/redoc.standalone.js" charset="UTF-8"></script>
</body>
</html>"""


@app.get("/docs", include_in_schema=False)
async def swagger_ui_html(request: Request):
    if not _SWAGGER_ASSETS_READY:
        return RedirectResponse(url="/redoc", status_code=307)
    openapi_url = _openapi_spec_url(request)
    # Use FastAPI’s template (correct Swagger UI 5 presets); load JS/CSS from vendored ``/swagger-assets``.
    resp = get_swagger_ui_html(
        openapi_url=openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="/swagger-assets/swagger-ui-bundle.js",
        swagger_css_url="/swagger-assets/swagger-ui.css",
        swagger_favicon_url="/swagger-assets/favicon-32x32.png",
        oauth2_redirect_url="/docs/oauth2-redirect",
    )
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@app.get("/redoc", include_in_schema=False)
async def redoc_html(request: Request):
    if not _REDOC_READY:
        u = _openapi_spec_url(request)
        return HTMLResponse(
            content=(
                "<!DOCTYPE html><html><body style=\"font-family:system-ui;padding:2rem\">"
                "<p>ReDoc bundle not installed. Open the raw spec:</p>"
                f"<p><a href=\"{html.escape(u)}\">{html.escape(u)}</a></p></body></html>"
            ),
            headers={"Cache-Control": "no-store"},
        )
    openapi_url = _openapi_spec_url(request)
    return HTMLResponse(
        content=_redoc_html_page(openapi_url=openapi_url),
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/docs/oauth2-redirect", include_in_schema=False)
async def swagger_ui_oauth2_redirect():
    return get_swagger_ui_oauth2_redirect_html()


def custom_openapi():
    """Strip long marketing copy from the OpenAPI document (Swagger / clients)."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description="",
        routes=app.routes,
    )
    info = schema.setdefault("info", {})
    info["description"] = ""
    for key in ("contact", "license", "termsOfService"):
        info.pop(key, None)
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


# ──────────────────────────────────────────────
# MIDDLEWARE
# ──────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    # Must be False when allow_origins is "*"(wildcard); Safari rejects the invalid combo with credentialed requests.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# EXCEPTION HANDLERS
# ──────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Returns structured validation errors matching wizard field-level error display.
    Format: { field_path: [error_message] }
    """
    errors = []
    for error in exc.errors():
        err_type = error.get("type", "")
        if err_type == "json_invalid":
            loc_parts = [str(x) for x in error.get("loc", ()) if x != "body"]
            hint = (
                "Request body is not valid JSON (check around that position). "
                "Use double quotes for keys and strings, no trailing commas, no comments."
            )
            field_label = f"body (char {loc_parts[0]})" if loc_parts else "body"
            errors.append({"field": field_label, "message": hint, "type": err_type})
            continue
        loc = " → ".join(str(l) for l in error["loc"] if l != "body")
        errors.append({
            "field": loc,
            "message": error["msg"],
            "type": err_type,
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation failed. Please correct the highlighted fields.",
            "errors": errors,
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An internal error occurred. Please try again.",
            "detail": str(exc),
        }
    )


# ──────────────────────────────────────────────
# ROUTERS
# ──────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(wizard.router, prefix=API_PREFIX)
app.include_router(sow.router, prefix=API_PREFIX)
app.include_router(approvals.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(billing.router, prefix=API_PREFIX)
if settings.REVIEWER_API_ENABLED:
    app.include_router(reviewer.router, prefix=API_PREFIX)


# ──────────────────────────────────────────────
# ROOT
# ──────────────────────────────────────────────

@app.get("/", tags=["Health"], summary="API health check")
async def root():
    return {
        "service": "GlimmoraTeam AI SOW Generator API",
        "version": "1.0.0",
        "status": "running",
        "docs_swagger": "/docs",
        "docs_redoc": "/redoc",
        "openapi_json": "/openapi.json",
        "hint": "If /docs is blank in Safari, use /redoc (ReDoc) or download /openapi.json.",
    }


@app.get("/health", tags=["Health"], summary="Detailed health check")
async def health():
    from app.core.database import get_database
    try:
        db = get_database()
        await db.command("ping")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "version": "1.0.0",
    }

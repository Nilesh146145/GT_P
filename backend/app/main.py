"""
GlimmoraTeam — AI SOW Generator API
FastAPI + MongoDB backend for the 10-step SOW Wizard.
"""
from __future__ import annotations


from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_oauth2_redirect_html
from starlette.requests import Request
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import DatabaseNotAvailable, close_db, connect_db
from app.project_portfolio import router as project_portfolio_router
from app.routers import auth, mfa, oauth, reviewer, wizard, sow, approvals, users, manual_sow_router
from app.routers.decomposition import decomposition_router
from app.routers.decomposition.webhook import router as decomposition_webhook_router
from app.openapi_docs import get_swagger_ui_html_with_tag_order
from app.services.manual_sow.errors import ManualSowSpecException


# ──────────────────────────────────────────────
# LIFESPAN
# ──────────────────────────────────────────────

_log = logging.getLogger(__name__)


def _check_email_validator_for_openapi() -> None:
    """
    Pydantic EmailStr triggers importlib.metadata.version('email-validator') when building
    /openapi.json. If the module imports but metadata is missing, Swagger shows 500 with
    detail \"email-validator\".
    """
    try:
        import email_validator  # noqa: F401
    except ImportError:
        _log.critical(
            "OpenAPI/Swagger will fail: email_validator not importable. "
            "Run: .venv/bin/pip install 'email-validator>=2.0.0,<3'"
        )
        return
    try:
        from importlib.metadata import version

        version("email-validator")
    except Exception:
        _log.warning(
            "pip metadata for email-validator missing or unreadable (OpenAPI still works: "
            "see app/__init__.py patch). For a clean venv: pip install --force-reinstall "
            "'email-validator>=2.0.0,<3'"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_email_validator_for_openapi()
    await connect_db()
    try:
        await create_indexes()
    except Exception:
        _log.exception("MongoDB index creation failed; continuing startup")
    yield
    await close_db()


async def create_indexes():
    """Create MongoDB indexes for performance."""
    from app.core.database import get_database, is_db_connected

    if not is_db_connected():
        print("Skipping MongoDB indexes (no database connection).")
        return

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

    # Manual SOW intake
    await db["manual_sows"].create_index("public_id", unique=True)
    await db["manual_sows"].create_index("created_by_user_id")
    await db["manual_sows"].create_index("status")
    await db["manual_sows"].create_index("created_at")
    await db["manual_sow_files"].create_index([("created_by_user_id", 1), ("hash_sha256", 1), ("uploaded_at", -1)])
    await db["manual_sow_extraction_items"].create_index([("sow_public_id", 1), ("category", 1), ("review_state", 1)])
    await db["manual_sow_gap_items"].create_index([("sow_public_id", 1), ("severity", 1)])
    await db["manual_sow_approval_messages"].create_index([("sow_public_id", 1), ("sent_at", -1)])
    await db["manual_sow_audit_log"].create_index([("sow_public_id", 1), ("created_at", -1)])

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

    # MFA
    await db["user_totp_credentials"].create_index("user_id", unique=True)
    await db["user_mfa_recovery_codes"].create_index("user_id")
    await db["mfa_setup_pending"].create_index("user_id", unique=True)
    await db["mfa_setup_pending"].create_index("expires_at", expireAfterSeconds=0)
    await db["mfa_audit_log"].create_index("user_id")
    await db["mfa_audit_log"].create_index("created_at")

    # Reviewer
    await db["reviewer_assignments"].create_index("reviewer_user_id")
    await db["reviewer_assignments"].create_index([("reviewer_user_id", 1), ("status", 1)])
    await db["reviewer_evidence"].create_index("reviewer_user_id")
    await db["reviewer_evidence"].create_index([("evidence_id", 1), ("reviewer_user_id", 1)])
    await db["reviewer_recommendations"].create_index("reviewer_user_id")
    await db["reviewer_recommendations"].create_index([("evidence_id", 1), ("reviewer_user_id", 1)])
    await db["reviewer_projects"].create_index("reviewer_user_id")
    await db["reviewer_projects"].create_index([("project_id", 1), ("reviewer_user_id", 1)])

    await db["decomposition_plans"].create_index("plan_id", unique=True)
    await db["decomposition_plans"].create_index([("enterprise_profile_id", 1), ("kicked_off", 1)])
    await db["decomposition_plans"].create_index("enterprise_profile_id")
    await db["decomposition_plans"].create_index("sow_reference")

    if settings.BILLING_API_ENABLED:
        await db["billing_invoices"].create_index("payer_id")
        await db["billing_invoices"].create_index("status")
        await db["billing_invoices"].create_index("created_at")
        await db["billing_invoices"].create_index("due_at")
        await db["billing_invoice_items"].create_index("invoice_id")
        await db["billing_payments"].create_index("invoice_id")
        await db["billing_payments"].create_index("status")
        await db["billing_payments"].create_index("method")
        await db["billing_payments"].create_index("created_at")
        await db["billing_refunds"].create_index("payment_id")
        await db["billing_refunds"].create_index("invoice_id")
        await db["billing_refunds"].create_index("created_at")

    print("MongoDB indexes created.")


# ──────────────────────────────────────────────
# OPENAPI / SWAGGER — tag order: auth first, then SOW flow (wizard → AI review → manual)
# ──────────────────────────────────────────────

_OPENAPI_TAGS = [
    {"name": "Authentication", "description": "Login, register, tokens, refresh."},
    {"name": "OAuth", "description": "Google / Microsoft SSO (after auth concepts)."},
    {"name": "MFA", "description": "TOTP and MFA verification flows."},
    {
        "name": "Users & Enterprise",
        "description": "Profiles and enterprise settings.",
    },
    {
        "name": "SOW Wizard",
        "description": "**Primary path — start here:** 10-step wizard under **`/api/v1/wizards`**.",
    },
    {
        "name": "AI Draft Review",
        "description": (
            "**After the wizard:** draft SOWs under **`/api/v1/sows`** (plural). "
            "Review and refine AI-generated content before approvals."
        ),
    },
    {
        "name": "Approval Pipeline",
        "description": "Approval stages for wizard-generated SOWs.",
    },
    {
        "name": "Manual SOW",
        "description": (
            "**Alternate / late path:** upload an existing document under **`/api/v1/sow`** (singular) — "
            "typically **after** exploring AI Draft Review, not instead of it. "
            "Commercial details: **`GET .../commercial-details`** may auto-fill **`aiGeneratedText`** "
            "in the response body when Section C unlocks (requires **`OPENAI_API_KEY`**); no separate generate route."
        ),
    },
    {"name": "NDA", "description": "NDA acceptance helpers."},
    {"name": "Reviewer", "description": "Reviewer workspace APIs."},
    {"name": "Billing", "description": "Invoices and payments (if enabled)."},
    {"name": "portfolio", "description": "Project portfolio."},
    {"name": "evidence", "description": "Portfolio evidence."},
    {"name": "projects", "description": "Portfolio projects."},
    {"name": "team", "description": "Portfolio team."},
    {"name": "milestones", "description": "Portfolio milestones."},
    {"name": "escalations", "description": "Portfolio escalations."},
    {"name": "commercial", "description": "Portfolio commercial tab."},
    {"name": "payments", "description": "Portfolio payments."},
    {"name": "Plans", "description": "Decomposition plans."},
    {"name": "Plan Actions", "description": "Plan actions."},
    {"name": "Tasks", "description": "Decomposition tasks."},
    {"name": "Checklist", "description": "Decomposition checklist."},
    {"name": "Summary", "description": "Plan summary."},
    {"name": "Task Detail", "description": "Task detail."},
    {"name": "Revision", "description": "Plan revision."},
    {"name": "Revised Plan", "description": "Revised plan output."},
    {"name": "Revision Detail", "description": "Revision detail."},
    {"name": "Plan Review Page", "description": "Plan review UI API."},
    {"name": "Internal — Decomposition", "description": "Internal webhooks (ops)."},
    {"name": "Health", "description": "Liveness and health."},
]

_OPENAPI_TAG_ORDER = [t["name"] for t in _OPENAPI_TAGS]


# ──────────────────────────────────────────────
# APP INSTANCE
# ──────────────────────────────────────────────

app = FastAPI(
    title="GlimmoraTeam — AI SOW Generator API",
    description="""
## AI Statement of Work Generator — 10-Step Wizard API

This API powers the complete SOW generation platform for GlimmoraTeam.

In **Swagger (`/docs`)**, tags are ordered: **Authentication → OAuth → MFA → Users & Enterprise → SOW Wizard → AI Draft Review → …**

### Recommended product flow
1. **SOW Wizard** — **`/api/v1/wizards`** (build the draft step by step).
2. **AI Draft Review** — **`/api/v1/sows`** (review / refine the AI-generated SOW).
3. **Manual SOW (optional)** — **`/api/v1/sow`** (upload a document **after** or **beside** the AI path — not the first step in the journey).

### Wizard Steps

| Step | Name | Type |
|------|------|------|
| 0 | Project Context & Discovery | **MANDATORY** |
| 1 | Project Identity & Scope | **MANDATORY** |
| 2 | Delivery & Technical Scope | **MANDATORY** |
| 3 | Integrations & User Management | Optional (−8% confidence) |
| 4 | Timeline, Team & Testing | Optional (−7% confidence) |
| 5 | Budget & Risk | **MANDATORY** |
| 6 | Quality Standards | Optional (−5% confidence) |
| 7 | Governance & Compliance | **MANDATORY** |
| 8 | Commercial & Legal | **MANDATORY** |
| 9 | Review & Generate | Final step |

### Generation Rules
- Steps **0, 1, 2, 5, 7, 8** must be completed before generation
- Data Sensitivity Level (Step 7) has **no default** — must be explicitly selected
- Non-discrimination confirmation (Step 7) is a **hard block**
- Hallucination prevention: **8 layers** checked before submission
- **[Submit for Approval]** permanently blocked if any red hallucination layer or unresolved prohibited clause

### Payment Schedule (Platform Standard)
30% on SOW onboarding (M1) · 35% on development completion (M2) · 35% on UAT sign-off (M3)

### Approval Pipeline
Business Owner → GlimmoraTeam Commercial → Legal → Security → Final Approver
    """,
    version="1.0.1",
    openapi_tags=_OPENAPI_TAGS,
    swagger_ui_parameters={
        "filter": True,
        "persistAuthorization": True,
    },
    contact={
        "name": "GlimmoraTeam Engineering",
        "email": "engineering@glimmora.team",
    },
    license_info={
        "name": "Proprietary",
    },
    lifespan=lifespan,
    docs_url=None,
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ──────────────────────────────────────────────
# MIDDLEWARE
# ──────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# EXCEPTION HANDLERS
# ──────────────────────────────────────────────

@app.exception_handler(ManualSowSpecException)
async def manual_sow_spec_exception_handler(request: Request, exc: ManualSowSpecException):
    return JSONResponse(status_code=exc.status_code, content=exc.body)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Returns structured validation errors matching wizard field-level error display.
    Format: { field_path: [error_message] }
    """
    errors = []
    for error in exc.errors():
        loc = " → ".join(str(l) for l in error["loc"] if l != "body")
        errors.append({
            "field": loc,
            "message": error["msg"],
            "type": error["type"],
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation failed. Please correct the highlighted fields.",
            "errors": errors,
        }
    )


@app.exception_handler(DatabaseNotAvailable)
async def database_not_available_handler(request: Request, exc: DatabaseNotAvailable):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "success": False,
            "message": "Database is not connected. Start MongoDB, set MONGODB_URL in backend/.env (or repo-root .env), then restart the API.",
            "detail": "database_unavailable",
            "hint": "Local example: MONGODB_URL=mongodb://127.0.0.1:27017 — or use your MongoDB Atlas connection string.",
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    _log.exception("Unhandled exception: %r", exc)
    detail = str(exc) or repr(exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An internal error occurred. Please try again.",
            "detail": detail,
        }
    )


# ──────────────────────────────────────────────
# ROUTERS
# ──────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(oauth.router, prefix=API_PREFIX)
app.include_router(mfa.router, prefix=API_PREFIX)
app.include_router(wizard.router, prefix=API_PREFIX)
app.include_router(sow.router, prefix=API_PREFIX)
app.include_router(approvals.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(manual_sow_router.router, prefix=API_PREFIX)
app.include_router(manual_sow_router.nda_router, prefix=API_PREFIX)
app.include_router(decomposition_router, prefix=API_PREFIX)
app.include_router(decomposition_webhook_router, prefix=API_PREFIX)
app.include_router(project_portfolio_router, prefix=API_PREFIX)
if settings.BILLING_API_ENABLED:
    from app.billing import router as billing_router

    app.include_router(billing_router, prefix=API_PREFIX)
if settings.REVIEWER_API_ENABLED:
    app.include_router(reviewer.router, prefix=API_PREFIX)


def custom_openapi():
    """Add Swagger hints so Bearer auth is entered correctly (token only, no 'Bearer ' prefix)."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    kw: dict = {
        "title": app.title,
        "version": app.version,
        "description": app.description,
        "routes": app.routes,
    }
    if getattr(app, "openapi_tags", None):
        kw["tags"] = app.openapi_tags

    openapi_schema = get_openapi(**kw)
    schemes = openapi_schema.get("components", {}).get("securitySchemes") or {}
    for scheme in schemes.values():
        if scheme.get("type") == "http" and scheme.get("scheme") == "bearer":
            scheme["description"] = (
                "Paste ONLY the JWT (the long string starting with eyJ). "
                "Do NOT type the word Bearer — this page adds Bearer automatically. "
                "If you type Bearer yourself, you get 401."
            )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# ──────────────────────────────────────────────
# SWAGGER UI (custom HTML so tag sidebar follows _OPENAPI_TAG_ORDER)
# ──────────────────────────────────────────────


def _swagger_ui_response(request: Request, page_title: str):
    root_path = request.scope.get("root_path", "").rstrip("/")
    openapi_url = root_path + (app.openapi_url or "/openapi.json")
    oauth2_redirect_url = app.swagger_ui_oauth2_redirect_url
    if oauth2_redirect_url:
        oauth2_redirect_url = root_path + oauth2_redirect_url
    return get_swagger_ui_html_with_tag_order(
        openapi_url=openapi_url,
        title=page_title,
        tag_order=_OPENAPI_TAG_ORDER,
        oauth2_redirect_url=oauth2_redirect_url,
        init_oauth=app.swagger_ui_init_oauth,
        swagger_ui_parameters=app.swagger_ui_parameters,
    )


@app.get("/docs", include_in_schema=False)
async def swagger_docs(request: Request):
    """Interactive OpenAPI docs; tag order matches the recommended product flow."""
    return _swagger_ui_response(request, f"{app.title} - Swagger UI")


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_oauth2_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/swagger", include_in_schema=False)
async def swagger_ui_fresh(request: Request):
    """Same spec and tag order as `/docs`; alternate URL if `/docs` is cached."""
    return _swagger_ui_response(request, f"{app.title} — Swagger UI")


# ──────────────────────────────────────────────
# ROOT
# ──────────────────────────────────────────────

@app.get("/", tags=["Health"], summary="API health check")
async def root(request: Request):
    """Includes absolute URLs so you can confirm you are on this server (port + host)."""
    base = str(request.base_url).rstrip("/")
    return {
        "service": "GlimmoraTeam AI SOW Generator API",
        "version": app.version,
        "status": "running",
        "you_are_here": base,
        "docs": f"{base}/docs",
        "swagger": f"{base}/swagger",
        "openapi_json": f"{base}/openapi.json",
        "redoc": f"{base}/redoc",
        "flow_order_note": (
            "Intended order: **SOW Wizard** (/api/v1/wizards) → **AI Draft Review** (/api/v1/sows) → "
            "optional **Manual SOW upload** (/api/v1/sow/). "
            "Swagger lists tags in this order; the UI step bar is implemented in the frontend app."
        ),
        "manual_sow_note": (
            "Manual upload: **/api/v1/sow/** (singular). Wizard + AI review: **/api/v1/sows/** (plural)."
        ),
        "manual_sow_example": f"{base}/api/v1/sow/upload",
    }


@app.head("/", include_in_schema=False)
async def root_head():
    """Render and load balancers often probe with HEAD; without this, FastAPI returns 405."""
    return Response(status_code=200)


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
        "version": app.version,
    }


@app.head("/health", include_in_schema=False)
async def health_head():
    """Lightweight probe for platforms that use HEAD (avoid DB work on every probe)."""
    return Response(status_code=200)

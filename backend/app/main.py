"""
GlimmoraTeam — AI SOW Generator API
FastAPI + MongoDB backend for the 10-step SOW Wizard.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import close_db, connect_db
from app.project_portfolio import router as project_portfolio_router
from app.routers import auth, mfa, oauth, reviewer, wizard, sow, approvals, users, manual_sow_router
from app.routers.decomposition import decomposition_router
from app.routers.decomposition.webhook import router as decomposition_webhook_router
from app.services.manual_sow.errors import ManualSowSpecException


# ──────────────────────────────────────────────
# LIFESPAN
# ──────────────────────────────────────────────

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
# APP INSTANCE
# ──────────────────────────────────────────────

app = FastAPI(
    title="GlimmoraTeam — AI SOW Generator API",
    description="""
## AI Statement of Work Generator — 10-Step Wizard API

This API powers the complete SOW generation platform for GlimmoraTeam.

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
    version="1.0.0",
    contact={
        "name": "GlimmoraTeam Engineering",
        "email": "engineering@glimmora.team",
    },
    license_info={
        "name": "Proprietary",
    },
    lifespan=lifespan,
    docs_url="/docs",
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

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
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
# ROOT
# ──────────────────────────────────────────────

@app.get("/", tags=["Health"], summary="API health check")
async def root():
    return {
        "service": "GlimmoraTeam AI SOW Generator API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
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
        "version": "1.0.0",
    }


@app.head("/health", include_in_schema=False)
async def health_head():
    """Lightweight probe for platforms that use HEAD (avoid DB work on every probe)."""
    return Response(status_code=200)

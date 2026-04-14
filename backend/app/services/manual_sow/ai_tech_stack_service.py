"""
OpenAI-backed Manual SOW — Tech & Integrations (Section C).

Model returns JSON with top-level key "AI-generated-text" whose value is an object:
{ "title", "tags", "AI-generated-tech-stack", "technologyStackLine", "scalabilityPerformance",
  "userManagementScope", "ssoRequired", "summary" } — persisted into ``techIntegrations`` on save.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.core.config import manual_sow_use_mock_ai_tech_stack, settings
from app.schemas.manual_sow.models import AiGeneratedTextContent
from app.schemas.manual_sow.manual_sow_platform_type import normalize_manual_sow_platform_type

_log = logging.getLogger(__name__)

_JSON_KEY = "AI-generated-text"

# Mock / quota-fallback lists: keep short (SOW-friendly); still ≥ MIN_STORED_AI_TECH_STACK_ITEMS in build_mock.
MOCK_AI_TECH_STACK_MAX_ITEMS = 12
_MIN_STORED_AI_TECH_STACK_ITEMS = 8  # keep in sync with manual_sow_service.MIN_STORED_AI_TECH_STACK_ITEMS

# Normalized (lowercase) names that belong to native/hybrid mobile clients — drop from stacks when platform is web/API/data-only.
_MOBILE_ONLY_TECH_KEYS = frozenset(
    {
        "flutter",
        "dart",
        "swift",
        "swiftui",
        "kotlin",
        "jetpack compose",
        "xcode",
        "android studio",
        "coroutines",
        "gradle",
        "testflight",
        "combine",
        "fastlane",
        "objective-c",
        "objc",
        "react native",
    }
)

_PLATFORMS_EXCLUDE_MOBILE_NATIVE_TOKENS = frozenset({"WEB_APPLICATION", "API_BACKEND_ONLY", "DATA_PLATFORM"})


def stored_ai_tech_stack_conflicts_with_delivery_scope(
    commercial_details: Dict[str, Any], ai_inner: Any
) -> bool:
    """
    True when ``deliveryScope.platformType`` is web/API/data-only but persisted AI still names
    native-mobile technologies. Used so GET commercial-details will regenerate instead of serving
    an old Mongo row that only matched the scope fingerprint (e.g. Flutter left from extraction text).
    """
    if not isinstance(ai_inner, dict):
        return False
    ds = (commercial_details or {}).get("deliveryScope") or {}
    pt = _delivery_scope_normalized_platform(ds) or "OTHER"
    if pt not in _PLATFORMS_EXCLUDE_MOBILE_NATIVE_TOKENS:
        return False

    names: List[str] = []
    ts = ai_inner.get("AI-generated-tech-stack")
    if ts is None:
        ts = ai_inner.get("tech_stack")
    if isinstance(ts, list):
        names.extend(str(x).strip() for x in ts if str(x).strip())
    tags = ai_inner.get("tags")
    if isinstance(tags, list):
        names.extend(str(x).strip() for x in tags if str(x).strip())
    line = str(ai_inner.get("technologyStackLine") or ai_inner.get("technology_stack_line") or "").strip()
    if line:
        for sep in ("\u00b7", "·"):
            if sep in line:
                for part in line.split(sep):
                    p = part.strip()
                    if "(" in p:
                        p = p.split("(", 1)[0].strip()
                    if p:
                        names.append(p)
                break
        else:
            p = line
            if "(" in p:
                p = p.split("(", 1)[0].strip()
            if p:
                names.append(p)

    for n in names:
        if n.lower() in _MOBILE_ONLY_TECH_KEYS:
            return True
    return False


def _delivery_scope_normalized_platform(ds: Dict[str, Any]) -> str:
    """Canonical ``platformType`` for branching (accepts human labels)."""
    raw = str((ds or {}).get("platformType") or (ds or {}).get("platform_type") or "").strip()
    n = normalize_manual_sow_platform_type(raw)
    return (n or raw).strip().upper()


def _nested_openai_error(body: Any) -> Optional[Dict[str, Any]]:
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return err
    return None


def _detail_from_openai_exception(exc: Exception) -> Dict[str, Any]:
    """Safe, actionable JSON for HTTP detail (no secrets)."""
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            BadRequestError,
            NotFoundError,
            PermissionDeniedError,
            RateLimitError,
        )
    except ImportError:
        return {
            "code": "OPENAI_ERROR",
            "message": (str(exc) or "OpenAI call failed.")[:800],
            "model": settings.MANUAL_SOW_OPENAI_MODEL,
        }

    model = settings.MANUAL_SOW_OPENAI_MODEL

    if isinstance(exc, APIConnectionError):
        return {
            "code": "OPENAI_CONNECTION_ERROR",
            "message": str(exc) or "Could not reach OpenAI (network, DNS, or TLS).",
            "model": model,
        }

    if isinstance(exc, APIStatusError):
        nested = _nested_openai_error(exc.body)
        provider_msg = None
        if nested:
            pm = nested.get("message")
            if isinstance(pm, str) and pm.strip():
                provider_msg = pm.strip()[:800]
        msg = provider_msg or exc.message or str(exc)
        detail: Dict[str, Any] = {
            "code": "OPENAI_HTTP_ERROR",
            "message": msg[:800],
            "httpStatus": exc.status_code,
            "model": model,
        }
        if exc.request_id:
            detail["openaiRequestId"] = exc.request_id
        et = (nested or {}).get("type") or exc.type
        ec = (nested or {}).get("code") or exc.code
        if et:
            detail["openaiErrorType"] = str(et)
        if ec:
            detail["openaiErrorCode"] = str(ec)
        if isinstance(exc, AuthenticationError):
            detail["code"] = "OPENAI_AUTH_ERROR"
            detail["hint"] = "Check OPENAI_API_KEY in backend/.env (restart server after edits)."
        elif isinstance(exc, PermissionDeniedError):
            detail["code"] = "OPENAI_PERMISSION_DENIED"
            detail["hint"] = "Key may lack chat/completions access or org billing is blocked."
        elif isinstance(exc, RateLimitError):
            quota_code = str((nested or {}).get("code") or "").lower()
            quota_type = str((nested or {}).get("type") or "").lower()
            if quota_code == "insufficient_quota" or quota_type == "insufficient_quota":
                detail["code"] = "OPENAI_INSUFFICIENT_QUOTA"
                detail["hint"] = (
                    "No credits or active billing on this OpenAI account. Open "
                    "https://platform.openai.com/account/billing and add a payment method or credits; "
                    "retrying without billing will not fix this. For local demos set "
                    "MANUAL_SOW_USE_MOCK_AI_TECH_STACK=true or MANUAL_SOW_AI_FALLBACK_ON_QUOTA=true in backend/.env."
                )
            else:
                detail["code"] = "OPENAI_RATE_LIMIT"
                detail["hint"] = (
                    "Too many requests in a short window; wait and retry or raise your organization rate limits."
                )
        elif isinstance(exc, NotFoundError):
            detail["code"] = "OPENAI_NOT_FOUND"
            detail["hint"] = (
                f"Often wrong model id: set MANUAL_SOW_OPENAI_MODEL in backend/.env (currently {model!r})."
            )
        elif isinstance(exc, BadRequestError):
            detail["code"] = "OPENAI_BAD_REQUEST"
            detail["hint"] = "Model may not support json_object response_format, or the request was rejected."
        return detail

    return {
        "code": "OPENAI_ERROR",
        "message": (str(exc) or "Unexpected error calling OpenAI.")[:800],
        "model": model,
    }
_SYSTEM_PROMPT = (
    "You assist with enterprise Statements of Work. "

    f'Return ONLY valid JSON with exactly one top-level key "{_JSON_KEY}". '
    f'Its value must be an object with keys: '

    '"title" (short string), '
    '"tags" (array of short strings), '

    '"AI-generated-tech-stack" (JSON array of 6–14 concrete technologies as strings — '
    "each must represent a real product or framework, no vague terms, no duplicates). "

    '"technologyStackLine" (string, required): one single line using ` · ` separator. '
    "Each item must be formatted as `Technology (role)` and reflect correct system layers. "

    "-----------------------------------"
    "CRITICAL PLATFORM RULES (STRICT)"
    "-----------------------------------"

    "You MUST strictly follow deliveryScope.platformType. "

    "PlatformType rules: "

    "WEB_APPLICATION → "
    "Include: React/Angular/Vue + backend (FastAPI/Node) + database + CDN. "
    "Do NOT include mobile technologies (Flutter, Swift, Kotlin, React Native). "

    "MOBILE_IOS → "
    "Include Swift/SwiftUI + backend + APIs. "

    "MOBILE_ANDROID → "
    "Include Kotlin/Jetpack Compose + backend. "

    "MOBILE_HYBRID → "
    "Include Flutter or React Native + backend. "

    "DESKTOP → "
    "Include Electron / .NET / native desktop frameworks. "

    "API_BACKEND_ONLY → "
    "Include ONLY backend stack (FastAPI, Node.js, DB, messaging). "
    "DO NOT include frontend frameworks unless explicitly mentioned. "

    "DATA_PLATFORM → "
    "Include data pipelines, ETL, warehouses (Airflow, Spark, Snowflake, BigQuery). "
    "DO NOT include UI frameworks unless explicitly required. "

    "FULL_STACK → "
    "Include both frontend and backend layers. "

    "-----------------------------------"
    "DEVELOPMENT SCOPE RULES (STRICT)"
    "-----------------------------------"

    "Follow deliveryScope.developmentScope: "

    "If Frontend is present → include client stack. "
    "If Backend is present → include APIs, services, database. "
    "If Integration is present → include messaging, APIs, third-party integrations. "

    "Do NOT generate partial stack when multiple layers are required. "

    "-----------------------------------"
    "OUTPUT REQUIREMENTS"
    "-----------------------------------"

    '"scalabilityPerformance" (string, 50–2000 chars): '
    "Only performance aspects: concurrency, p95 latency, autoscaling, caching, CDN. "

    '"userManagementScope" (string, 30–2000 chars): '
    "Roles, access patterns, SSO/IdP integration. "

    '"ssoRequired" (boolean): true if enterprise SSO expected. '

    '"summary" (string, 10–2000 chars): '
    "Short paragraph covering security, compliance, DR. "
    "Do NOT repeat stack or scalability text. "

    "-----------------------------------"
    "STRICT RULES"
    "-----------------------------------"

    "- DO NOT mix mobile and web stacks incorrectly. "
    "- DO NOT hallucinate technologies outside platformType. "
    "- DO NOT include unnecessary tools. "
    "- Use real-world technologies only. "
    "- Prefer industry-standard stacks. "
)


def _strip_code_fence(raw: str) -> str:
    t = (raw or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _extract_ai_text_object(parsed: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(parsed, dict):
        return None
    inner = parsed.get(_JSON_KEY)
    if isinstance(inner, dict):
        return inner
    return None


def _platform_type_stack_guidance(ds: Dict[str, Any]) -> Optional[str]:
    """Non-binding hints for the model; existing context still wins."""
    pt = _delivery_scope_normalized_platform(ds or {})
    if not pt:
        return None
    guidance = {
        "MOBILE_IOS": "Delivery platform type MOBILE_IOS: consider Swift / SwiftUI (or Objective-C only if implied).",
        "MOBILE_ANDROID": "Delivery platform type MOBILE_ANDROID: consider Kotlin (or Java only if implied).",
        "MOBILE_HYBRID": "Delivery platform type MOBILE_HYBRID: consider Flutter and/or React Native unless the document names a specific stack.",
        "WEB_APPLICATION": (
            "Delivery platform type WEB_APPLICATION: consider React, Angular, or Vue for SPA unless the document implies otherwise. "
            "Do not output Flutter/Dart/Swift/Kotlin/React Native as the primary client unless the document explicitly demands a mobile client alongside web."
        ),
        "FULL_STACK": "Delivery platform type FULL_STACK: suggest a coherent full-stack architecture (frontend + API + data) aligned with the document.",
        "API_BACKEND_ONLY": "Delivery platform type API_BACKEND_ONLY: focus on backend services (e.g. FastAPI, Node.js) and omit client UI unless explicitly required.",
        "DATA_PLATFORM": "Delivery platform type DATA_PLATFORM: emphasize ETL / pipelines / analytics tooling (e.g. Spark, Airflow, dbt, warehouse) as appropriate.",
        "DESKTOP": "Delivery platform type DESKTOP: consider desktop-appropriate stacks (e.g. Electron, .NET, Qt) only if implied by context.",
        "OTHER": "Delivery platform type OTHER: stay generic unless the document specifies technologies.",
    }
    return guidance.get(pt, f"Delivery platform type {pt}: align technologies with the stated scope.")


def _build_user_message(
    *,
    project_title: str,
    client_org: str,
    commercial_details: Dict[str, Any],
    body: Optional[Dict[str, Any]],
) -> str:
    bc = (commercial_details or {}).get("businessContext") or {}
    ds = (commercial_details or {}).get("deliveryScope") or {}
    ti = (commercial_details or {}).get("techIntegrations") or (commercial_details or {}).get("tech_integrations") or {}
    parts = [
        f"Project title: {project_title or 'Unknown'}",
        f"Client organisation: {client_org or 'Unknown'}",
        f"Business context (Section A): {json.dumps(bc, ensure_ascii=False, default=str)}",
        f"Delivery scope (Section B): {json.dumps(ds, ensure_ascii=False, default=str)}",
        f"Tech & Integrations section (may be partial): {json.dumps(ti, ensure_ascii=False, default=str)}",
    ]
    hint = _platform_type_stack_guidance(ds)
    if hint:
        parts.append(hint)
    pt_norm = _delivery_scope_normalized_platform(ds) or "OTHER"
    if pt_norm in _PLATFORMS_EXCLUDE_MOBILE_NATIVE_TOKENS:
        parts.append(
            "CRITICAL: deliveryScope.platformType is "
            f"{pt_norm} — exclude Flutter, Dart, Swift, Kotlin, React Native, and other native-mobile stacks "
            "unless the document text explicitly requires a mobile client in addition to this platform type."
        )
    dev = ds.get("developmentScope") or ds.get("development_scope") or []
    if isinstance(dev, list) and dev:
        parts.append(
            "developmentScope order: include technologies for each listed layer in sequence (Frontend → Backend → Integration as applicable); "
            "the tech stack array and summary must not collapse to a single-layer list while multiple layers are selected."
        )
    parts.append(
        "SOW output requirements: AI-generated-tech-stack must stay short (about 6–14 names) but cover each layer implied by "
        "platformType and developmentScope — no duplicate concepts, no exhaustive vendor dumps. "
        "The summary must follow the same layer order (not marketing fluff)."
    )
    if body:
        if body.get("technologyStackDraft") or body.get("technology_stack_draft"):
            parts.append(f"User draft technology stack: {body.get('technologyStackDraft') or body.get('technology_stack_draft')}")
        if body.get("scalabilityPerformance") or body.get("scalability_performance"):
            parts.append(f"Scalability / performance notes: {body.get('scalabilityPerformance') or body.get('scalability_performance')}")
        if body.get("userManagementScope") or body.get("user_management_scope"):
            parts.append(f"User management scope: {body.get('userManagementScope') or body.get('user_management_scope')}")
        if body.get("ssoRequired") is True or body.get("sso_required") is True:
            parts.append("SSO is required for this project.")
        if body.get("additionalContext") or body.get("additional_context"):
            parts.append(f"Additional context: {body.get('additionalContext') or body.get('additional_context')}")
    return "\n".join(parts)


_TECH_NAME_PATTERN = re.compile(
    r"\b("
    r"Docker|AWS|Azure|GCP|Kubernetes|PostgreSQL|MongoDB|MySQL|Redis|React|Angular|Vue|Next\.js|Nextjs|"
    r"FastAPI|Django|Flask|Node\.js|Nodejs|Python|TypeScript|Java|Swift|Kotlin|Flutter|Firebase|Electron|REST|GraphQL|Terraform|"
    r"OpenAI|GitHub Actions|Jenkins|nginx|Nginx|RabbitMQ|Kafka|Celery|Prometheus|Grafana|Datadog|Sentry"
    r")\b",
    re.IGNORECASE,
)


def _filter_conflicting_mobile_tokens(tech_stack: List[str], pt_label: str) -> List[str]:
    """Strip mobile-native tokens when delivery scope is web/API/data-only (stale ``technologyStack`` regex hits)."""
    if pt_label not in _PLATFORMS_EXCLUDE_MOBILE_NATIVE_TOKENS:
        return tech_stack
    return [t for t in tech_stack if t.strip().lower() not in _MOBILE_ONLY_TECH_KEYS]


def _stack_layer_slices(tech_stack: List[str]) -> tuple[List[str], List[str], List[str], List[str], List[str], List[str], List[str]]:
    """Layer buckets for ``technologyStackLine`` (same rules as mock Section C)."""
    fe = [
        t
        for t in tech_stack
        if t
        in {
            "TypeScript",
            "React",
            "Vite",
            "Angular",
            "Vue",
            "Next.js",
            "HTML5",
            "CSS3",
            "Flutter",
            "Dart",
            "Swift",
            "SwiftUI",
            "Kotlin",
            "Jetpack Compose",
            "Electron",
        }
    ]
    be = [
        t
        for t in tech_stack
        if t in {"Python", "FastAPI", "Node.js", "Django", "Uvicorn", "Pydantic", "Java", "Coroutines", "Combine"}
    ]
    data = [
        t
        for t in tech_stack
        if t
        in {
            "PostgreSQL",
            "MongoDB",
            "Redis",
            "Amazon RDS",
            "SQLAlchemy",
            "Alembic",
            "Amazon S3",
            "Firebase",
            "Apache Airflow",
            "dbt",
            "Apache Spark",
            "Great Expectations",
        }
    ]
    infra = [t for t in tech_stack if t in {"Docker", "AWS", "Amazon ECS", "Kubernetes", "Terraform", "Azure", "GCP"}]
    cicd = [t for t in tech_stack if t in {"Git", "GitHub Actions", "Jenkins"}]
    sec = [t for t in tech_stack if t in {"JWT", "OAuth 2.0", "OpenAPI"}]
    integ = [t for t in tech_stack if t in {"RabbitMQ", "Celery", "Webhooks", "Kafka", "REST", "GraphQL"}]
    return fe, be, data, infra, cicd, sec, integ


def _format_stack_line_for_tech_stack(tech_stack: List[str], pt_label: str) -> str:
    fe, be, data, infra, cicd, _sec, integ = _stack_layer_slices(tech_stack)
    return _format_concise_technology_stack_line(
        tech_stack=tech_stack,
        fe=fe,
        be=be,
        data=data,
        integ=integ,
        infra=infra,
        cicd=cicd,
        pt_label=pt_label,
    )


def sow_technology_catalog_for_delivery_scope(commercial_details: Dict[str, Any]) -> List[str]:
    """
    Platform- and scope-aware baseline catalog for SOW Tech & Integrations (mock / quota fallback).
    Branches on ``deliveryScope.platformType`` and uses ``developmentScope`` (frontend/backend/integration)
    to add or omit server-side items. Merged with regex hits from ``technologyStack`` in
    ``build_mock_ai_tech_stack_payload``. Does not call OpenAI.
    """
    ds = (commercial_details or {}).get("deliveryScope") or {}
    pt = _delivery_scope_normalized_platform(ds)
    dev = ds.get("developmentScope") or ds.get("development_scope") or []
    if not isinstance(dev, list):
        dev = []
    blob = " ".join(str(x).lower() for x in dev)
    has_fe = "frontend" in blob
    has_be = "backend" in blob
    has_int = "integration" in blob or "api" in blob

    _MOBILE_PTS = frozenset({"MOBILE_HYBRID", "MOBILE_IOS", "MOBILE_ANDROID"})
    # Empty developmentScope on mobile: assume a typical shipped product (client + APIs + integrations).
    if pt in _MOBILE_PTS and not dev:
        has_fe = True
        has_be = True
        has_int = True

    out: List[str] = []
    seen: set[str] = set()

    def add(*items: str) -> None:
        for it in items:
            k = it.lower()
            if k not in seen:
                seen.add(k)
                out.append(it)

    def add_cloud_data_auth_cicd_obs() -> None:
        """Compact web/API backing services (mock lists stay short)."""
        add(
            "PostgreSQL",
            "Redis",
            "OpenAPI",
            "JWT",
            "Docker",
            "AWS",
            "Git",
            "GitHub Actions",
            "Terraform",
        )

    def add_integration_extras() -> None:
        if has_int:
            add("Kafka", "Webhooks")

    def add_mobile_backend_compact() -> None:
        """Backend for mobile SOWs when Backend/Integration is in scope — short list."""
        add("Python", "FastAPI", "PostgreSQL", "Redis", "OpenAPI", "JWT", "Docker", "AWS", "Git", "GitHub Actions")
        add_integration_extras()

    # ── Web: SPA-first; add BFF/API only when scope includes backend or integration ──
    if pt == "WEB_APPLICATION":
        if has_fe or not dev:
            add("TypeScript", "React", "Vite", "HTML5", "CSS3")
        else:
            add("TypeScript", "React", "Vite")
        if has_be or has_int:
            add("Python", "FastAPI", "Uvicorn", "Pydantic")
            add_cloud_data_auth_cicd_obs()
        else:
            add("Docker", "AWS", "Git", "GitHub Actions", "REST", "OpenAPI", "JWT", "Redis")
        add_integration_extras()

    elif pt == "FULL_STACK":
        if has_fe or not dev:
            add("TypeScript", "React", "Vite", "HTML5", "CSS3")
        if has_be or not dev:
            add("Python", "FastAPI", "Uvicorn", "Pydantic")
        add(
            "PostgreSQL",
            "Redis",
            "REST",
            "OpenAPI",
            "JWT",
            "Docker",
            "AWS",
            "Git",
            "GitHub Actions",
            "Terraform",
        )
        add_integration_extras()

    elif pt == "API_BACKEND_ONLY":
        add(
            "Python",
            "FastAPI",
            "Uvicorn",
            "Pydantic",
            "PostgreSQL",
            "Redis",
            "REST",
            "OpenAPI",
            "JWT",
            "Docker",
            "AWS",
            "Git",
            "GitHub Actions",
            "Terraform",
        )
        add_integration_extras()

    elif pt == "MOBILE_HYBRID":
        # Client stack first so ``out[:MOCK_AI_TECH_STACK_MAX_ITEMS]`` keeps UI technologies when truncating.
        add("Flutter", "Dart", "Firebase", "REST", "Git", "GitHub Actions")
        if has_be or has_int:
            add_mobile_backend_compact()
        if not (has_be or has_int):
            add("PostgreSQL", "OpenAPI", "JWT")

    elif pt == "MOBILE_IOS":
        add("Swift", "SwiftUI", "Xcode", "REST", "Git", "GitHub Actions", "TestFlight")
        if has_be or has_int:
            add_mobile_backend_compact()
        if not (has_be or has_int):
            add("PostgreSQL", "OpenAPI", "JWT")

    elif pt == "MOBILE_ANDROID":
        add("Kotlin", "Jetpack Compose", "Android Studio", "REST", "Firebase", "Git", "GitHub Actions")
        if has_be or has_int:
            add_mobile_backend_compact()
        if not (has_be or has_int):
            add("PostgreSQL", "OpenAPI", "JWT")

    elif pt == "DATA_PLATFORM":
        add(
            "Python",
            "Apache Airflow",
            "dbt",
            "Apache Spark",
            "Kafka",
            "PostgreSQL",
            "Amazon S3",
            "AWS",
            "Docker",
            "Git",
            "GitHub Actions",
        )
        add_integration_extras()

    elif pt == "DESKTOP":
        add(
            "TypeScript",
            "Electron",
            "React",
            "Node.js",
            "REST",
            "OpenAPI",
            "JWT",
            "PostgreSQL",
            "Docker",
            "AWS",
            "Git",
            "GitHub Actions",
        )
        add_integration_extras()

    elif pt == "OTHER" or not pt:
        add("PostgreSQL", "Redis", "REST", "OpenAPI", "Docker", "AWS", "Git", "GitHub Actions", "JWT")
        if has_fe:
            add("TypeScript", "React", "Vite")
        if has_be:
            add("Python", "FastAPI", "Uvicorn")
        if has_int:
            add("Kafka", "Webhooks")

    else:
        add("PostgreSQL", "Docker", "AWS", "REST", "OpenAPI", "Git", "GitHub Actions", "Redis", "Python", "FastAPI")

    def ensure_development_scope_layers() -> None:
        """Guarantee layers implied by developmentScope are represented (SOW flow: FE → BE → integration)."""
        if has_fe and pt in ("WEB_APPLICATION", "FULL_STACK"):
            if not any(k in seen for k in ("react", "angular", "vue", "vite", "next.js", "nextjs")):
                add("TypeScript", "React", "Vite", "HTML5", "CSS3")
        elif has_fe and pt in _MOBILE_PTS:
            if pt == "MOBILE_HYBRID":
                if not any(
                    k in seen
                    for k in ("flutter", "dart", "swift", "swiftui", "kotlin", "jetpack compose")
                ):
                    add("Flutter", "Dart", "Firebase")
            elif pt == "MOBILE_IOS":
                if "swift" not in seen and "swiftui" not in seen:
                    add("Swift", "SwiftUI", "Xcode")
            elif pt == "MOBILE_ANDROID":
                if "kotlin" not in seen:
                    add("Kotlin", "Jetpack Compose", "Android Studio")
        elif has_fe and pt == "DESKTOP":
            if "electron" not in seen:
                add("TypeScript", "Electron", "React", "Node.js")
        if has_be:
            if not any(k in seen for k in ("fastapi", "django", "flask", "nodejs", "node.js")):
                add("Python", "FastAPI", "Uvicorn", "OpenAPI")
            if "postgresql" not in seen:
                add("PostgreSQL", "Redis")
        if has_int:
            if "rabbitmq" not in seen and "kafka" not in seen:
                add("RabbitMQ", "Webhooks")

    ensure_development_scope_layers()
    return out[:MOCK_AI_TECH_STACK_MAX_ITEMS]


def _format_concise_technology_stack_line(
    *,
    tech_stack: List[str],
    fe: List[str],
    be: List[str],
    data: List[str],
    integ: List[str],
    infra: List[str],
    cicd: List[str],
    pt_label: str,
) -> str:
    """
    One UI-friendly line: ``Name (role) · Name (role) · …`` (middle dot), like the Manual SOW Section C textarea.
    """
    parts: List[str] = []
    mobile = pt_label in {"MOBILE_HYBRID", "MOBILE_IOS", "MOBILE_ANDROID"}
    ts_join = " ".join(tech_stack)

    def add(name: str, role: str) -> None:
        n = name.strip()
        if not n:
            return
        entry = f"{n} ({role})"
        if entry not in parts:
            parts.append(entry)

    if fe:
        add(fe[0], "mobile client" if mobile else "frontend")
    if be:
        pick = next((x for x in be if "node" in x.lower()), be[0])
        add(pick, "API layer")

    if any("Firebase" in x for x in tech_stack) and mobile:
        add("Firebase", "mobile backend services")

    pg = next((x for x in data if "PostgreSQL" in x or "postgres" in x.lower()), None)
    if pg:
        add(str(pg).split()[0] if " " in str(pg) else pg, "primary database")

    mongo = next((x for x in data if "Mongo" in x), None)
    if mongo and not pg:
        add(mongo, "document store")

    rd = next((x for x in data if "Redis" in x or "redis" in x.lower()), None)
    if rd:
        add(rd, "caching/sessions")

    if "AWS" in ts_join:
        if "ECS" in ts_join or "Amazon ECS" in ts_join:
            add("AWS ECS + RDS", "hosting")
        else:
            add("AWS", "hosting")
        if not mobile and pt_label in {"WEB_APPLICATION", "FULL_STACK"}:
            add("CloudFront", "CDN")

    if integ:
        ik = next((x for x in integ if x in {"Kafka", "RabbitMQ", "Webhooks"}), integ[0])
        add(ik, "messaging" if ik == "Kafka" else "integrations")

    ga = next((x for x in cicd if "GitHub" in x), None)
    if ga:
        add(ga, "CI/CD")
    elif "GitHub Actions" in ts_join:
        add("GitHub Actions", "CI/CD")
    elif cicd:
        add(cicd[0], "CI/CD")

    if len(parts) < 3:
        return " · ".join(f"{x} (stack component)" for x in tech_stack[:10])

    return " · ".join(parts[:12])


def build_mock_ai_tech_stack_payload(
    *,
    project_title: str,
    client_org: str,
    commercial_details: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Deterministic Section-C-shaped payload from commercial_details (no OpenAI).
    Merges extracted tokens with a platform-aware full-stack catalog for SOW use.
    """
    ti = (commercial_details or {}).get("techIntegrations") or {}
    ts = str(ti.get("technologyStack") or "").strip()
    bc = (commercial_details or {}).get("businessContext") or {}
    pv = str(bc.get("projectVision") or "").strip()
    ds = (commercial_details or {}).get("deliveryScope") or {}
    pt_label = _delivery_scope_normalized_platform(ds) or "OTHER"

    tech_stack: List[str] = []
    seen: set[str] = set()
    for m in _TECH_NAME_PATTERN.finditer(ts):
        raw = m.group(1)
        if raw.lower() == "nextjs":
            norm = "Next.js"
        elif raw.lower() in ("nodejs", "node.js"):
            norm = "Node.js"
        elif raw.upper() == "AWS":
            norm = "AWS"
        elif raw.lower() == "nginx":
            norm = "nginx"
        else:
            norm = raw[:1].upper() + raw[1:].lower() if len(raw) > 1 else raw.upper()
        key = norm.lower()
        if key not in seen:
            seen.add(key)
            tech_stack.append(norm)

    for name in sow_technology_catalog_for_delivery_scope(commercial_details):
        k = name.lower()
        if k not in seen:
            seen.add(k)
            tech_stack.append(name)

    tech_stack = _filter_conflicting_mobile_tokens(tech_stack, pt_label)
    seen = {t.lower() for t in tech_stack}

    tech_stack = tech_stack[:MOCK_AI_TECH_STACK_MAX_ITEMS]
    if len(tech_stack) < _MIN_STORED_AI_TECH_STACK_ITEMS:
        for name in ("PostgreSQL", "Docker", "AWS", "REST", "Git", "OpenAPI", "JWT", "Redis"):
            if name.lower() not in seen:
                seen.add(name.lower())
                tech_stack.append(name)
            if len(tech_stack) >= _MIN_STORED_AI_TECH_STACK_ITEMS:
                break
    tech_stack = tech_stack[:MOCK_AI_TECH_STACK_MAX_ITEMS]

    title_prefix = {
        "WEB_APPLICATION": "Web application technology baseline",
        "FULL_STACK": "Full-stack (web + API + data) technology baseline",
        "API_BACKEND_ONLY": "API and backend-services technology baseline",
        "MOBILE_HYBRID": "Cross-platform mobile technology baseline",
        "MOBILE_IOS": "iOS native technology baseline",
        "MOBILE_ANDROID": "Android native technology baseline",
        "DATA_PLATFORM": "Data and analytics platform technology baseline",
        "DESKTOP": "Desktop application technology baseline",
        "OTHER": "Technology baseline",
    }.get(pt_label, "Technology baseline")
    title = (f"{title_prefix} — {project_title}".strip())[:240] or "Technology baseline"
    tags = tech_stack[:8]

    dev_list = ds.get("developmentScope") or ds.get("development_scope") or []
    stack_line = _format_stack_line_for_tech_stack(tech_stack, pt_label)

    layers_note = ""
    if isinstance(dev_list, list) and dev_list:
        layers_note = f"Layers: {', '.join(str(x).strip() for x in dev_list if str(x).strip())}. "

    summary = (
        f"{layers_note}"
        f"Security, compliance, and continuity for {client_org or 'the client'} ({pt_label}): align with client policies, "
        "document data classification, encryption in transit/at rest, and DR expectations. Confirm legal review before sign-off."
    )
    if pv:
        summary += f" Vision context: {pv[:280].strip()}"
    if len(summary) > 2000:
        summary = summary[:1997] + "..."

    scalability_txt = (
        f"Target concurrent users and p95 API latency SLOs appropriate for {pt_label}. "
        "Autoscale stateless tiers within agreed min/max; use Redis or equivalent for sessions and read-heavy paths where applicable. "
        "Run load tests before UAT; document rollback for capacity changes."
    )
    if pt_label in ("WEB_APPLICATION", "FULL_STACK"):
        scalability_txt += " Use a CDN for static assets with explicit cache TTLs."

    user_mgmt_txt = (
        "Role-based access for admins, operators, and end users with least privilege. "
        "When SSO applies, integrate the client corporate IdP (e.g. Microsoft Entra ID, Okta) and map directory groups to application roles."
    )

    inner = {
        "title": title,
        "tags": tags,
        "AI-generated-tech-stack": tech_stack[:MOCK_AI_TECH_STACK_MAX_ITEMS],
        "technologyStackLine": stack_line,
        "scalabilityPerformance": scalability_txt[:2000],
        "userManagementScope": user_mgmt_txt[:2000],
        "ssoRequired": True,
        "summary": summary,
    }
    validated = AiGeneratedTextContent.model_validate(inner)
    return validated.model_dump(mode="json", by_alias=True)


def _align_openai_inner_payload_to_platform(
    inner: Dict[str, Any], commercial_details: Dict[str, Any]
) -> Dict[str, Any]:
    """If the model echoes mobile tokens for a web/API/data scope, drop them and backfill from the platform catalog."""
    ts_key = "AI-generated-tech-stack"
    raw_ts = inner.get(ts_key)
    if not isinstance(raw_ts, list):
        return inner
    ds = (commercial_details or {}).get("deliveryScope") or {}
    pt_label = _delivery_scope_normalized_platform(ds) or "OTHER"
    ts = [str(x).strip() for x in raw_ts if str(x).strip()]
    filtered = _filter_conflicting_mobile_tokens(ts, pt_label)
    if filtered == ts:
        return inner
    seen = {x.lower() for x in filtered}
    for n in sow_technology_catalog_for_delivery_scope(commercial_details or {}):
        if n.lower() not in seen:
            seen.add(n.lower())
            filtered.append(n)
        if len(filtered) >= _MIN_STORED_AI_TECH_STACK_ITEMS:
            break
    if len(filtered) < _MIN_STORED_AI_TECH_STACK_ITEMS:
        for name in ("PostgreSQL", "Docker", "AWS", "REST", "Git", "OpenAPI", "JWT", "Redis"):
            nk = name.lower()
            if nk not in seen:
                seen.add(nk)
                filtered.append(name)
            if len(filtered) >= _MIN_STORED_AI_TECH_STACK_ITEMS:
                break
    filtered = filtered[:MOCK_AI_TECH_STACK_MAX_ITEMS]
    out = dict(inner)
    out[ts_key] = filtered
    out["technologyStackLine"] = _format_stack_line_for_tech_stack(filtered, pt_label)
    out["tags"] = filtered[:8]
    return out


async def generate_ai_tech_stack(
    *,
    project_title: str,
    client_org: str,
    commercial_details: Dict[str, Any],
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Call OpenAI and return a dict (by_alias) for Mongo `ai_generated_text`; GET commercial-details exposes it as `aiGeneratedText`.
    Includes hyphenated key `AI-generated-tech-stack` as list of strings.
    """
    if manual_sow_use_mock_ai_tech_stack():
        _log.info("MANUAL_SOW_USE_MOCK_AI_TECH_STACK: returning mock tech stack (OpenAI not called).")
        return build_mock_ai_tech_stack_payload(
            project_title=project_title,
            client_org=client_org,
            commercial_details=commercial_details or {},
        )

    if not settings.openai_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "OPENAI_NOT_CONFIGURED",
                "message": "OPENAI_API_KEY is not set. Add it to the server environment to use Generate AI tech stack.",
            },
        )

    try:
        from openai import AsyncOpenAI
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "OPENAI_SDK_MISSING",
                "message": "openai package is not installed. Run: pip install -r requirements.txt",
            },
        ) from e

    user_msg = _build_user_message(
        project_title=project_title,
        client_org=client_org,
        commercial_details=commercial_details or {},
        body=body,
    )

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        completion = await client.chat.completions.create(
            model=settings.MANUAL_SOW_OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.35,
        )
    except Exception as e:
        _log.exception("OpenAI tech stack generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_detail_from_openai_exception(e),
        ) from e

    raw = (completion.choices[0].message.content or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "OPENAI_EMPTY", "message": "The model returned an empty response."},
        )

    try:
        parsed = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as e:
        _log.warning("OpenAI tech stack JSON parse failed: %s | raw=%s", e, raw[:500])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "OPENAI_INVALID_JSON", "message": "The model response was not valid JSON."},
        ) from e

    inner = _extract_ai_text_object(parsed)
    if not inner:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "OPENAI_BAD_PAYLOAD",
                "message": f'The model JSON must include an object value for "{_JSON_KEY}" with title, tags, technologyStackLine, scalabilityPerformance, userManagementScope, ssoRequired, and summary.',
            },
        )

    inner = _align_openai_inner_payload_to_platform(inner, commercial_details or {})

    try:
        validated = AiGeneratedTextContent.model_validate(inner)
    except Exception as e:
        _log.warning("AI text schema validation failed: %s | inner=%s", e, inner)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "OPENAI_BAD_SHAPE",
                "message": "The model JSON did not match required shape (title, tags, AI-generated-tech-stack array, technologyStackLine, scalabilityPerformance, userManagementScope, ssoRequired, summary).",
            },
        ) from e

    return validated.model_dump(mode="json", by_alias=True)


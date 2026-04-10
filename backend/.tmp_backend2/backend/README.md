# GlimmoraTeam — AI SOW Generator API

FastAPI + MongoDB backend for the 10-Step Statement of Work Wizard.

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- MongoDB 6+ running locally (default: `mongodb://localhost:27017`)

### 2. Install dependencies

```bash
cd sow_backend
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set MONGODB_URL, SECRET_KEY
```

### 4. Run the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open Swagger UI

```
http://localhost:8000/docs
```

ReDoc (alternative):
```
http://localhost:8000/redoc
```

---

## Project Structure

```
sow_backend/
├── app/
│   ├── main.py                  # FastAPI app, middleware, routers
│   ├── core/
│   │   ├── config.py            # Settings (env vars)
│   │   ├── database.py          # MongoDB motor connection + collection accessors
│   │   └── security.py          # JWT auth, password hashing
│   ├── routers/
│   │   ├── auth.py              # Register, login, /me
│   │   ├── wizard.py            # All 10 step endpoints + generate
│   │   ├── sow.py               # AI Draft Review endpoints
│   │   ├── approvals.py         # 5-stage approval pipeline
│   │   └── users.py             # User search (approver picker)
│   ├── schemas/
│   │   ├── common.py            # Shared enums, base response
│   │   ├── step0.py             # Step 0 — Project Context & Discovery
│   │   ├── step1_2.py           # Steps 1–2 — Scope + Delivery
│   │   ├── step3_5.py           # Steps 3–5 — Integrations, Timeline, Budget
│   │   ├── step6_8.py           # Steps 6–8 — Quality, Governance, Legal
│   │   └── wizard.py            # Wizard/SOW documents, request/response
│   └── services/
│       ├── wizard_service.py    # Core wizard CRUD + generation orchestration
│       ├── confidence.py        # AI confidence scoring + hallucination layers
│       └── sow_generator.py     # SOW content generation + risk scoring
├── tests/
│   └── test_wizard.py           # Full test suite (pytest-asyncio)
├── requirements.txt
├── pytest.ini
└── .env.example
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register enterprise user |
| POST | `/api/v1/auth/login` | Login — returns Bearer token |
| GET | `/api/v1/auth/me` | Current user profile |

All wizard/SOW endpoints require `Authorization: Bearer <token>` header.

---

### Wizard Lifecycle

| Method | Endpoint | Step Type | Description |
|--------|----------|-----------|-------------|
| POST | `/api/v1/wizards` | — | Create new wizard session |
| GET | `/api/v1/wizards` | — | List all wizards (current user) |
| GET | `/api/v1/wizards/{id}` | — | Get full wizard state |
| PUT | `/api/v1/wizards/{id}/steps/0` | **MANDATORY** | Project Context & Discovery |
| PUT | `/api/v1/wizards/{id}/steps/1` | **MANDATORY** | Project Identity & Scope |
| PUT | `/api/v1/wizards/{id}/steps/2` | **MANDATORY** | Delivery & Technical Scope |
| PUT | `/api/v1/wizards/{id}/steps/3` | Optional | Integrations & User Management |
| POST | `/api/v1/wizards/{id}/steps/3/skip` | Optional | Skip Step 3 (−8% confidence) |
| PUT | `/api/v1/wizards/{id}/steps/4` | Optional | Timeline, Team & Testing |
| POST | `/api/v1/wizards/{id}/steps/4/skip` | Optional | Skip Step 4 (−7% confidence) |
| PUT | `/api/v1/wizards/{id}/steps/5` | **MANDATORY** | Budget & Risk |
| PUT | `/api/v1/wizards/{id}/steps/6` | Optional | Quality Standards |
| POST | `/api/v1/wizards/{id}/steps/6/skip` | Optional | Skip Step 6 (−5% confidence) |
| PUT | `/api/v1/wizards/{id}/steps/7` | **MANDATORY** | Governance & Compliance |
| PUT | `/api/v1/wizards/{id}/steps/8` | **MANDATORY** | Commercial & Legal |
| GET | `/api/v1/wizards/{id}/steps/9/summary` | — | Review summary + readiness check |
| POST | `/api/v1/wizards/{id}/generate` | — | Generate SOW with AI |

---

### AI Draft Review

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/sows` | List all SOWs |
| GET | `/api/v1/sows/{id}` | Full SOW with quality metrics + generated content |
| GET | `/api/v1/sows/{id}/hallucination-analysis` | 8-layer hallucination breakdown |
| GET | `/api/v1/sows/{id}/risk-assessment` | Weighted risk score breakdown |
| POST | `/api/v1/sows/{id}/action` | submit / request_changes / reject_regenerate |

---

### Approval Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/approvals/{sow_id}` | Full 5-stage pipeline status |
| POST | `/api/v1/approvals/{sow_id}/stage/{1-5}/decide` | Record approve/reject/changes decision |

---

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/search?q=name` | Search users for approver picker |
| GET | `/api/v1/users/{id}` | Get user profile by ID |

---

## Validation Rules (from spec)

| Rule | Code | Description |
|------|------|-------------|
| Mandatory steps block generation | WIZ-001 | Steps 0,1,2,5,7,8 must be complete |
| Data Sensitivity no default | WIZ-002 | Must explicitly select — never defaults |
| Approvers required | WIZ-003 | Both Business Owner + Final Approver needed |
| Industry Other requires text | WIZ-004 | Free-text required when "Other" selected |
| Budget max ≥ min | WIZ-005 | Enforced at field level |
| Non-discrimination hard block | WIZ-006 | Hard block — cannot be overridden |
| Personal data → privacy law required | WIZ-007 | Conditional mandatory |
| Migration → technical detail required | WIZ-008 | Conditional mandatory |
| UAT sign-off authority required | WIZ-009 | Triggers M3 billing milestone |
| Business objectives measurable | WIZ-010 | At least one target value required |
| Browser+device matrix | WIZ-011 | At least one browser and one device |

---

## Confidence Scoring Weights

| Step | Weight | Mandatory |
|------|--------|-----------|
| 0 — Project Context & Discovery | 20% | ✅ |
| 1 — Project Identity & Scope | 18% | ✅ |
| 2 — Delivery & Technical Scope | 15% | ✅ |
| 3 — Integrations & User Management | 8% | Optional |
| 4 — Timeline, Team & Testing | 7% | Optional |
| 5 — Budget & Risk | 12% | ✅ |
| 6 — Quality Standards | 5% | Optional |
| 7 — Governance & Compliance | 10% | ✅ |
| 8 — Commercial & Legal | 5% | ✅ |

Score thresholds: `< 60%` = Low (warn) · `60–89%` = Medium · `≥ 90%` = Ready to generate.

---

## Hallucination Prevention Layers

| Layer | Name | Activates After |
|-------|------|----------------|
| 1 | Template Selection Validation | Step 1 |
| 2 | Scope Boundary Enforcement | Step 1 |
| 3 | Clause Library Matching | Step 7 (Data Sensitivity) |
| 4 | Cross-Step Consistency Check | Step 2 |
| 5 | Compliance Alignment | Step 7 |
| 6 | Prohibited Clause Detection | Step 7 (Non-discrimination) |
| 7 | Business Context Anchoring | Step 0 |
| 8 | Evidence Pack Gate Validation | Step 4 |

Red layers = hard block on `[Submit for Approval]`. Cannot be overridden by any enterprise user.

---

## Running Tests

```bash
# Requires MongoDB running on localhost:27017
pytest tests/ -v

# Run specific test
pytest tests/test_wizard.py::test_full_generate_flow -v

# Run unit tests only (no DB needed)
pytest tests/test_wizard.py -k "confidence or hallucination" -v
```

---

## MongoDB Collections

| Collection | Purpose |
|------------|---------|
| `users` | Enterprise user accounts |
| `wizards` | Wizard sessions (all 10 steps stored as subdocuments) |
| `sows` | Generated SOW documents with quality metrics |
| `approvals` | Stage-by-stage approval pipeline records |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DATABASE_NAME` | `sow_generator` | Database name |
| `SECRET_KEY` | (required) | JWT signing secret — min 32 chars |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token TTL |
| `MIN_BUDGET_INR` | `500000` | Platform minimum (₹5,00,000) |
| `MIN_BUDGET_USD` | `6000` | Platform minimum ($6,000) |

---

## Payment Schedule (Platform Standard — not configurable)

```
30%  on SOW onboarding        (M1)
35%  on development completion (M2)
35%  on UAT sign-off           (M3)

All payments due before production go-live.
```

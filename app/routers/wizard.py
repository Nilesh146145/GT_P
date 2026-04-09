"""
Wizard Router — all 10-step wizard endpoints.
Each step has its own typed endpoint with full Pydantic validation.
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Body
from typing import Any

from app.core.security import get_current_user
from app.schemas.common import BaseResponse
from app.schemas.step0 import Step0Input
from app.schemas.step1_2 import Step1Input, Step2Input
from app.schemas.step3_5 import Step3Input, Step4Input, Step5Input
from app.schemas.step6_8 import Step6Input, Step7Input, Step8Input
from app.schemas.wizard import (
    WizardCreateRequest, WizardCreateResponse,
    StepSaveResponse, SkipStepRequest, SkipStepResponse,
    Step9Input, GenerateSOWResponse, SOWActionRequest
)
from app.services import wizard_service

router = APIRouter(prefix="/wizards", tags=["SOW Wizard"])


# ══════════════════════════════════════════════
# WIZARD LIFECYCLE
# ══════════════════════════════════════════════

@router.post("", response_model=WizardCreateResponse, status_code=201,
             summary="Create a new SOW wizard session")
async def create_wizard(
    req: WizardCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Creates a new wizard in draft state. Returns wizard_id for all subsequent calls.
    The wizard auto-saves every 30 seconds on the frontend.
    Draft wizards resume from the SOW Repository.
    """
    wizard_id = await wizard_service.create_wizard(req.enterprise_id, current_user["id"])
    return WizardCreateResponse(wizard_id=wizard_id)


@router.get("", response_model=BaseResponse, summary="List all wizards for current user")
async def list_wizards(current_user: dict = Depends(get_current_user)):
    wizards = await wizard_service.list_wizards(current_user["id"])
    return BaseResponse(data=wizards)


@router.get("/{wizard_id}", response_model=BaseResponse, summary="Get full wizard state")
async def get_wizard(
    wizard_id: str = Path(..., description="Wizard ID"),
    current_user: dict = Depends(get_current_user)
):
    """Returns complete wizard document including all saved step data, confidence scores, and hallucination layers."""
    wizard = await wizard_service.get_wizard(wizard_id, current_user["id"])
    return BaseResponse(data=wizard)


# ══════════════════════════════════════════════
# STEP 0 — Project Context & Discovery (MANDATORY)
# ══════════════════════════════════════════════

@router.put("/{wizard_id}/steps/0", response_model=StepSaveResponse,
            summary="[MANDATORY] Save Step 0 — Project Context & Discovery")
async def save_step_0(
    wizard_id: str,
    data: Step0Input,
    current_user: dict = Depends(get_current_user)
):
    """
    **MANDATORY — Cannot skip.**

    Step 0 is the most important step in the wizard. It captures the WHY behind the project.
    Every piece of information entered here anchors every generated clause to explicit enterprise intent.

    Sections:
    - **A**: Project Vision, SMART Business Objectives, Pain Points, Business Criticality
    - **B**: Current State (As-Is) and Desired Future State (To-Be)
    - **C**: Target End Users — profiles with age, tech literacy, device, accessibility needs
    - **D**: Success Metrics / KPIs and Definition of Project Success
    """
    return await wizard_service.save_step(wizard_id, current_user["id"], 0, data.model_dump())


# ══════════════════════════════════════════════
# STEP 1 — Project Identity & Scope (MANDATORY)
# ══════════════════════════════════════════════

@router.put("/{wizard_id}/steps/1", response_model=StepSaveResponse,
            summary="[MANDATORY] Save Step 1 — Project Identity & Scope")
async def save_step_1(
    wizard_id: str,
    data: Step1Input,
    current_user: dict = Depends(get_current_user)
):
    """
    **MANDATORY — Cannot skip.**

    Establishes project formal identity, functional requirements (feature modules, user roles,
    key business workflows), and scope boundaries (exclusions, assumptions, constraints, data migration).

    - Feature modules drive task decomposition and acceptance criteria generation.
    - Out-of-scope exclusions generate enforceable exclusion clauses.
    - Data migration scope triggers conditional fields in Step 2.
    """
    return await wizard_service.save_step(wizard_id, current_user["id"], 1, data.model_dump())


# ══════════════════════════════════════════════
# STEP 2 — Delivery & Technical Scope (MANDATORY)
# ══════════════════════════════════════════════

@router.put("/{wizard_id}/steps/2", response_model=StepSaveResponse,
            summary="[MANDATORY] Save Step 2 — Delivery & Technical Scope")
async def save_step_2(
    wizard_id: str,
    data: Step2Input,
    current_user: dict = Depends(get_current_user)
):
    """
    **MANDATORY — Cannot skip.**

    Answers the most commercially consequential question: what exactly is GlimmoraTeam contracted to deliver?

    - Development scope (frontend, backend, API, DB, CI/CD)
    - UI/UX design scope
    - Deployment scope (cloud provider, environments, containerisation)
    - Go-live and hypercare scope
    - Technology stack (used for tech-specific task generation and skill matching)

    Section C (data migration technical detail) is conditional on Step 1 migration = In Scope.
    """
    return await wizard_service.save_step(wizard_id, current_user["id"], 2, data.model_dump())


# ══════════════════════════════════════════════
# STEP 3 — Integrations & User Management (OPTIONAL)
# ══════════════════════════════════════════════

@router.put("/{wizard_id}/steps/3", response_model=StepSaveResponse,
            summary="[OPTIONAL] Save Step 3 — Integrations & User Management")
async def save_step_3(
    wizard_id: str,
    data: Step3Input,
    current_user: dict = Depends(get_current_user)
):
    """
    **Optional — skippable. Skipping reduces AI confidence by ~8%.**

    Per-integration detail: direction, protocol, auth, data format, sandbox credentials, error handling SLA.
    Each integration generates a dedicated clause. Also covers SSO, user registration, password policy,
    audit logging, approval workflows, notifications, and scheduled jobs.
    """
    return await wizard_service.save_step(wizard_id, current_user["id"], 3, data.model_dump())


@router.post("/{wizard_id}/steps/3/skip", response_model=SkipStepResponse,
             summary="Skip Step 3 — Integrations & User Management")
async def skip_step_3(
    wizard_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Skips Step 3. Confidence penalty: ~8%."""
    return await wizard_service.skip_step(wizard_id, current_user["id"], 3)


# ══════════════════════════════════════════════
# STEP 4 — Timeline, Team & Testing (OPTIONAL)
# ══════════════════════════════════════════════

@router.put("/{wizard_id}/steps/4", response_model=StepSaveResponse,
            summary="[OPTIONAL] Save Step 4 — Timeline, Team & Testing")
async def save_step_4(
    wizard_id: str,
    data: Step4Input,
    current_user: dict = Depends(get_current_user)
):
    """
    **Optional — skippable. Skipping reduces AI confidence by ~7%.**

    Timeline, milestones with acceptance criteria, team composition, required roles (feeds APG matching),
    and full testing scope.

    ⚠️ **The UAT Sign-off Authority designated here is the exact person whose platform action triggers
    the M3 billing milestone.** Designate correctly.
    """
    return await wizard_service.save_step(wizard_id, current_user["id"], 4, data.model_dump())


@router.post("/{wizard_id}/steps/4/skip", response_model=SkipStepResponse,
             summary="Skip Step 4 — Timeline, Team & Testing")
async def skip_step_4(
    wizard_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Skips Step 4. Confidence penalty: ~7%."""
    return await wizard_service.skip_step(wizard_id, current_user["id"], 4)


# ══════════════════════════════════════════════
# STEP 5 — Budget & Risk (MANDATORY)
# ══════════════════════════════════════════════

@router.put("/{wizard_id}/steps/5", response_model=StepSaveResponse,
            summary="[MANDATORY] Save Step 5 — Budget & Risk")
async def save_step_5(
    wizard_id: str,
    data: Step5Input,
    current_user: dict = Depends(get_current_user)
):
    """
    **MANDATORY — Cannot skip.**

    Stage 2 Commercial Review cannot proceed without a declared budget range.
    Budget min/max is validated against platform minimum engagement threshold.
    Known risks generate proportionate mitigation and contingency clauses.

    Payment schedule (display only): 30% M1 · 35% M2 · 35% M3.
    """
    return await wizard_service.save_step(wizard_id, current_user["id"], 5, data.model_dump())


# ══════════════════════════════════════════════
# STEP 6 — Quality Standards (OPTIONAL)
# ══════════════════════════════════════════════

@router.put("/{wizard_id}/steps/6", response_model=StepSaveResponse,
            summary="[OPTIONAL] Save Step 6 — Quality Standards")
async def save_step_6(
    wizard_id: str,
    data: Step6Input,
    current_user: dict = Depends(get_current_user)
):
    """
    **Optional — skippable. Skipping reduces AI confidence by ~5%.**

    Project-level acceptance criteria applied globally to every deliverable.
    Browser/device compatibility matrix (required to prevent scope disputes).
    SLA/uptime target, code review policy, documentation requirements,
    reporting/analytics scope, offline support, and localisation.
    """
    return await wizard_service.save_step(wizard_id, current_user["id"], 6, data.model_dump())


@router.post("/{wizard_id}/steps/6/skip", response_model=SkipStepResponse,
             summary="Skip Step 6 — Quality Standards")
async def skip_step_6(
    wizard_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Skips Step 6. Confidence penalty: ~5%."""
    return await wizard_service.skip_step(wizard_id, current_user["id"], 6)


# ══════════════════════════════════════════════
# STEP 7 — Governance & Compliance (MANDATORY)
# ══════════════════════════════════════════════

@router.put("/{wizard_id}/steps/7", response_model=StepSaveResponse,
            summary="[MANDATORY] Save Step 7 — Governance & Compliance")
async def save_step_7(
    wizard_id: str,
    data: Step7Input,
    current_user: dict = Depends(get_current_user)
):
    """
    **MANDATORY — Cannot skip.**

    Feeds 3 hallucination prevention layers simultaneously:
    - Layer 6 (prohibited clause detection — ethical constraints)
    - Layer 5 (compliance alignment — regulatory frameworks)
    - Layer 3 (clause library selection — data sensitivity)

    ⚠️ **Data Sensitivity Level has NO DEFAULT — must be explicitly selected.**
    Hard block on wizard completion if Non-Discrimination checkbox is unchecked.
    Personal Data = Yes makes Privacy Law and DPA Required mandatory.
    """
    return await wizard_service.save_step(wizard_id, current_user["id"], 7, data.model_dump())


# ══════════════════════════════════════════════
# STEP 8 — Commercial & Legal (MANDATORY)
# ══════════════════════════════════════════════

@router.put("/{wizard_id}/steps/8", response_model=StepSaveResponse,
            summary="[MANDATORY] Save Step 8 — Commercial & Legal")
async def save_step_8(
    wizard_id: str,
    data: Step8Input,
    current_user: dict = Depends(get_current_user)
):
    """
    **MANDATORY — Cannot skip. Entirely new step.**

    Captures the commercial and legal terms that generate the most post-delivery disputes:
    IP ownership, source code rights, third-party licensing cost responsibility,
    warranty period, and change request process.

    These are foundational legal provisions. Without them, the generated SOW is legally incomplete.
    Feeds Stage 3 Legal Review specifically.
    """
    return await wizard_service.save_step(wizard_id, current_user["id"], 8, data.model_dump())


# ══════════════════════════════════════════════
# STEP 9 — Review & Generate
# ══════════════════════════════════════════════

@router.get("/{wizard_id}/steps/9/summary", response_model=BaseResponse,
            summary="Get Step 9 review summary — all inputs + confidence + readiness check")
async def get_step_9_summary(
    wizard_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Returns the full Step 9 review payload:
    - Complete summary of all 10 steps (entered value or 'Not specified' / 'Skipped')
    - Step completion indicators (green / amber / red)
    - AI Confidence Score with advisory
    - Blocking errors (if any mandatory steps incomplete)
    - Hallucination layer statuses
    """
    wizard = await wizard_service.get_wizard(wizard_id, current_user["id"])
    errors = await wizard_service.validate_for_generation(wizard)

    confidence = wizard.get("confidence_score", 0)
    if confidence < 60:
        confidence_advisory = "Low Confidence — More Input Recommended. More detail yields a higher-quality, development-ready SOW."
        confidence_status = "low"
    elif confidence < 90:
        confidence_advisory = "Moderate confidence — consider completing optional steps for a stronger SOW."
        confidence_status = "medium"
    else:
        confidence_advisory = "Above threshold — ready to generate."
        confidence_status = "ready"

    step_indicators = {}
    mandatory = {0, 1, 2, 5, 7, 8}
    skipped = set(wizard.get("steps_skipped", []))
    completed = set(wizard.get("steps_completed", []))

    for i in range(9):
        if i in completed:
            step_indicators[i] = "green"
        elif i in skipped:
            step_indicators[i] = "amber"
        elif i in mandatory:
            step_indicators[i] = "red"
        else:
            step_indicators[i] = "not_started"

    return BaseResponse(data={
        "wizard_id": wizard_id,
        "confidence_score": confidence,
        "confidence_status": confidence_status,
        "confidence_advisory": confidence_advisory,
        "step_indicators": step_indicators,
        "steps_completed": sorted(completed),
        "steps_skipped": sorted(skipped),
        "blocking_errors": errors,
        "can_generate": len(errors) == 0,
        "hallucination_layers": wizard.get("hallucination_layers", []),
        "step_data_summary": {
            f"step_{i}": "completed" if i in completed else ("skipped" if i in skipped else "not_started")
            for i in range(9)
        }
    })


@router.post("/{wizard_id}/generate", response_model=BaseResponse,
             summary="Generate SOW with AI — triggers full document generation")
async def generate_sow(
    wizard_id: str,
    step9: Step9Input,
    current_user: dict = Depends(get_current_user)
):
    """
    **Final generation trigger.**

    Enabled only when:
    - Steps 0, 1, 2, 5, 7, and 8 complete with all required fields
    - Business Owner Approver and Final Approver designated

    **Generation:** When `OPENAI_API_KEY` is set (and `SOW_USE_OPENAI` is true), the SOW body is produced with **OpenAI** using model **`SOW_OPENAI_MODEL`** (default `gpt-4o-mini`). Otherwise a deterministic template is used. On LLM failure, the API falls back to the template automatically.

    Post-generation: hallucination checks → risk score → persist draft.

    Returns `sow_id` for use in the AI Draft Review endpoints.
    """
    result = await wizard_service.generate_sow(wizard_id, current_user["id"], step9.model_dump())
    return BaseResponse(
        message="SOW generated successfully.",
        data=result
    )

"""
Wizard Service — core CRUD and step-management logic.
"""

from datetime import datetime, date
from typing import Any, Dict, List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.core.database import (
    get_approvals_collection,
    get_sows_collection,
    get_wizards_collection,
)
from app.services.confidence import compute_confidence, compute_hallucination_layers, SKIP_PENALTIES
from app.services.sow_generator import generate_sow_content, run_hallucination_checks, compute_risk_score
from app.schemas.common import WizardStatus, SOWStatus

# Steps that are mandatory
MANDATORY_STEPS = {0, 1, 2, 5, 7, 8}
SKIPPABLE_STEPS = {3, 4, 6}


def _data_migration_in_scope(wizard: Dict) -> bool:
    """True when Step 1 declares data migration in scope (WIZ-008)."""
    s1c = (wizard.get("step_1") or {}).get("section_c") or {}
    dm = s1c.get("data_migration") or {}
    return bool(dm.get("in_scope"))


def _step2_migration_detail_satisfied(step_2: Optional[Dict]) -> bool:
    """Step 2 Section C must document ETL / transformation when migration is in scope."""
    if not step_2:
        return False
    sec_c = step_2.get("section_c") or {}
    if not sec_c:
        return False
    return bool(sec_c.get("etl_approach")) and bool(sec_c.get("transformation_complexity"))


def _sanitise_for_mongo(obj: Any) -> Any:
    """Recursively convert datetime.date -> datetime.datetime so BSON can encode it."""
    if isinstance(obj, datetime):
        return obj
    if isinstance(obj, date):
        return datetime(obj.year, obj.month, obj.day)
    if isinstance(obj, dict):
        return {k: _sanitise_for_mongo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitise_for_mongo(i) for i in obj]
    return obj




# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _serialize(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def _get_wizard_or_404(wizard_id: str, user_id: str) -> dict:
    col = get_wizards_collection()
    try:
        obj_id = ObjectId(wizard_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid wizard ID format.")
    doc = await col.find_one({"_id": obj_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Wizard not found.")
    if doc.get("created_by_user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return _serialize(doc)


# ──────────────────────────────────────────────
# CREATE
# ──────────────────────────────────────────────

async def create_wizard(enterprise_id: str, user_id: str) -> str:
    col = get_wizards_collection()
    now = datetime.utcnow()
    doc = {
        "enterprise_id": enterprise_id,
        "created_by_user_id": user_id,
        "status": WizardStatus.draft,
        "current_step": 0,
        "steps_completed": [],
        "steps_skipped": [],
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "hallucination_layers": [],
        **{f"step_{i}": None for i in range(10)},
        "last_saved": now,
        "created_at": now,
        "updated_at": now,
    }
    result = await col.insert_one(doc)
    return str(result.inserted_id)


# ──────────────────────────────────────────────
# SAVE STEP
# ──────────────────────────────────────────────

async def save_step(
    wizard_id: str,
    user_id: str,
    step: int,
    step_data: Any
) -> Dict:
    """Saves a single step's data and recomputes confidence."""

    wizard = await _get_wizard_or_404(wizard_id, user_id)
    col = get_wizards_collection()

    if wizard["status"] in (WizardStatus.submitted, WizardStatus.approved):
        raise HTTPException(
            status_code=409, detail="Cannot modify a submitted or approved wizard."
        )

    # Validate mandatory step cannot be skipped
    if step in MANDATORY_STEPS and step_data is None:
        raise HTTPException(
            status_code=422,
            detail=f"Step {step} is mandatory and cannot be saved as empty."
        )

    # Remove from skipped if user comes back to fill it
    steps_skipped: List[int] = wizard.get("steps_skipped", [])
    if step in steps_skipped:
        steps_skipped.remove(step)

    # WIZ-008 — block saving Step 2 without migration technical detail when Step 1 requires it
    if step == 2 and _data_migration_in_scope(wizard) and not _step2_migration_detail_satisfied(step_data):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Step 1 marks data migration in scope. Provide Step 2 Section C with "
                "etl_approach and transformation_complexity before saving."
            ),
        )

    # Mark step as completed
    steps_completed: List[int] = wizard.get("steps_completed", [])
    if step not in steps_completed:
        steps_completed.append(step)

    # Build full wizard data for confidence computation
    full_data = {f"step_{i}": wizard.get(f"step_{i}") for i in range(9)}
    full_data[f"step_{step}"] = step_data

    breakdown = compute_confidence(full_data, steps_skipped)
    hallucination_layers = compute_hallucination_layers(steps_completed)
    layers_active = sum(1 for l in hallucination_layers if l["active"])
    now = datetime.utcnow()

    step_data = _sanitise_for_mongo(step_data)
    await col.update_one(
        {"_id": ObjectId(wizard_id)},
        {"$set": {
            f"step_{step}": step_data,
            "steps_completed": sorted(steps_completed),
            "steps_skipped": sorted(steps_skipped),
            "confidence_score": breakdown["overall"],
            "confidence_breakdown": breakdown,
            "hallucination_layers": hallucination_layers,
            "current_step": max(wizard.get("current_step", 0), step),
            "last_saved": now,
            "updated_at": now,
        }}
    )

    return {
        "wizard_id": wizard_id,
        "step": step,
        "confidence_score": breakdown["overall"],
        "confidence_breakdown": breakdown,
        "hallucination_layers_active": layers_active,
        "steps_completed": sorted(steps_completed),
        "steps_skipped": sorted(steps_skipped),
        "validation_errors": [],
        "warnings": _generate_warnings(step, step_data, breakdown["overall"]),
    }


def _generate_warnings(step: int, data: Any, confidence: float) -> List[str]:
    warnings = []
    if confidence < 60:
        warnings.append(f"AI Confidence {confidence}% — Add more detail to improve quality.")
    if step == 0 and data:
        sec_a = (data.get("section_a") or {}) if isinstance(data, dict) else {}
        if len(sec_a.get("business_objectives", [])) < 2:
            warnings.append("Adding 2+ SMART business objectives significantly improves acceptance criteria quality.")
    return warnings


# ──────────────────────────────────────────────
# SKIP STEP
# ──────────────────────────────────────────────

async def skip_step(wizard_id: str, user_id: str, step: int) -> Dict:
    if step in MANDATORY_STEPS:
        raise HTTPException(
            status_code=422,
            detail=f"Step {step} is mandatory and cannot be skipped."
        )

    wizard = await _get_wizard_or_404(wizard_id, user_id)
    col = get_wizards_collection()

    steps_skipped: List[int] = wizard.get("steps_skipped", [])
    steps_completed: List[int] = wizard.get("steps_completed", [])

    if step not in steps_skipped:
        steps_skipped.append(step)
    if step in steps_completed:
        steps_completed.remove(step)

    full_data = {f"step_{i}": wizard.get(f"step_{i}") for i in range(9)}
    breakdown = compute_confidence(full_data, steps_skipped)
    penalty = SKIP_PENALTIES.get(step, 0)

    now = datetime.utcnow()
    await col.update_one(
        {"_id": ObjectId(wizard_id)},
        {"$set": {
            "steps_skipped": sorted(steps_skipped),
            "steps_completed": sorted(steps_completed),
            "confidence_score": breakdown["overall"],
            "confidence_breakdown": breakdown,
            "last_saved": now,
            "updated_at": now,
        }}
    )

    return {
        "wizard_id": wizard_id,
        "step": step,
        "skipped": True,
        "confidence_penalty": float(penalty),
        "new_confidence_score": breakdown["overall"],
        "message": f"Step {step} skipped. Confidence reduced by ~{penalty}%. Skipping optional steps reduces SOW quality."
    }


# ──────────────────────────────────────────────
# GET WIZARD
# ──────────────────────────────────────────────

async def get_wizard(wizard_id: str, user_id: str) -> Dict:
    return await _get_wizard_or_404(wizard_id, user_id)


async def list_wizards(user_id: str) -> List[Dict]:
    col = get_wizards_collection()
    cursor = col.find({"created_by_user_id": user_id}).sort("created_at", -1)
    results = []
    async for doc in cursor:
        results.append(_serialize(doc))
    return results


# ──────────────────────────────────────────────
# GENERATE SOW
# ──────────────────────────────────────────────

async def validate_for_generation(wizard: Dict) -> List[str]:
    """Returns list of blocking errors. Empty = can generate."""
    errors = []
    steps_completed = wizard.get("steps_completed", [])

    for step in MANDATORY_STEPS:
        if step not in steps_completed:
            step_names = {
                0: "Project Context & Discovery",
                1: "Project Identity & Scope",
                2: "Delivery & Technical Scope",
                5: "Budget & Risk",
                7: "Governance & Compliance",
                8: "Commercial & Legal",
            }
            errors.append(
                f"Required step incomplete: Step {step} — {step_names.get(step, '')} has required fields that must be filled."
            )

    # Check data sensitivity — no default allowed
    s7c = (wizard.get("step_7") or {}).get("section_c") or {}
    if not s7c.get("data_sensitivity_level"):
        errors.append("Data Sensitivity Level must be selected before generating. No default is applied.")

    # Check non-discrimination
    s7a = (wizard.get("step_7") or {}).get("section_a") or {}
    if not s7a.get("non_discrimination_confirmed"):
        errors.append("The non-discrimination confirmation is mandatory for all SOWs on GlimmoraTeam. This cannot be skipped.")

    # WIZ-008 — migration in scope → Step 2 technical detail
    if _data_migration_in_scope(wizard):
        if not _step2_migration_detail_satisfied(wizard.get("step_2")):
            errors.append(
                "WIZ-008: Data migration is in scope — complete Step 2 Section C "
                "(ETL approach and transformation complexity)."
            )

    # WIZ-009 — Step 4 completed → UAT sign-off authority (defense in depth)
    steps_done = wizard.get("steps_completed", [])
    if 4 in steps_done:
        s4c = (wizard.get("step_4") or {}).get("section_c") or {}
        uat = s4c.get("uat") or {}
        name = (uat.get("signoff_authority_name") or "").strip()
        title = (uat.get("signoff_authority_title") or "").strip()
        if not name or not title:
            errors.append(
                "WIZ-009: UAT sign-off authority name and title are required when Step 4 is completed."
            )

    # WIZ-010 — measurable business objectives
    s0a = (wizard.get("step_0") or {}).get("section_a") or {}
    for obj in s0a.get("business_objectives") or []:
        if not isinstance(obj, dict):
            errors.append("WIZ-010: Each business objective must include objective text and a measurable target.")
            break
        ob = (obj.get("objective") or "").strip()
        mt = (obj.get("measurable_target") or "").strip()
        if not ob:
            errors.append("WIZ-010: Each business objective must include an objective statement.")
            break
        if not mt:
            errors.append("WIZ-010: Each business objective must include a measurable target.")
            break

    return errors


async def generate_sow(wizard_id: str, user_id: str, step9_data: Dict) -> Dict:
    wizard = await _get_wizard_or_404(wizard_id, user_id)

    # Validate generation prerequisites
    errors = await validate_for_generation(wizard)
    if not step9_data.get("business_owner_approver_id"):
        errors.append("Please designate a Business Owner Approver before generating.")
    if not step9_data.get("final_approver_id"):
        errors.append("Please designate a Final Approver before generating.")

    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Cannot generate SOW — validation errors must be resolved.", "errors": errors}
        )

    full_data = {f"step_{i}": wizard.get(f"step_{i}") for i in range(9)}
    steps_completed = wizard.get("steps_completed", [])
    hallucination_layers = run_hallucination_checks(full_data, steps_completed)
    red_layers = [l for l in hallucination_layers if l.get("status") == "red"]
    if red_layers:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Cannot generate SOW — resolve red hallucination prevention layers first.",
                "errors": [f"{l['name']}: {l.get('detail', '')}" for l in red_layers],
            },
        )

    col_wiz = get_wizards_collection()
    col_sow = get_sows_collection()

    # Mark wizard as generating
    await col_wiz.update_one(
        {"_id": ObjectId(wizard_id)},
        {"$set": {"status": WizardStatus.generating, "step_9": step9_data, "updated_at": datetime.utcnow()}}
    )

    # Run generation (hallucination_layers already computed for gating + SOW storage)
    generated = generate_sow_content(full_data)
    risk_info = compute_risk_score(full_data)
    breakdown = compute_confidence(full_data, wizard.get("steps_skipped", []))

    # Completeness
    total_sections = len(generated["sections"])
    confident_sections = sum(1 for s in generated["sections"] if s["confidence"] >= 70)
    completeness_pct = round((confident_sections / total_sections) * 100, 1) if total_sections else 0

    if completeness_pct >= 90:
        completeness_status = "Complete"
    elif completeness_pct >= 70:
        completeness_status = "Near complete"
    else:
        completeness_status = "Incomplete"

    hallucination_flags = sum(1 for l in hallucination_layers if l["status"] == "red")

    quality_metrics = {
        "overall_confidence": breakdown["overall"],
        "risk_score": risk_info["risk_score"],
        "risk_level": risk_info["risk_level"],
        "hallucination_flags": hallucination_flags,
        "completeness_pct": completeness_pct,
        "completeness_status": completeness_status,
    }

    now = datetime.utcnow()
    sow_doc = {
        "wizard_id": wizard_id,
        "enterprise_id": wizard["enterprise_id"],
        "created_by_user_id": user_id,
        "status": SOWStatus.draft,
        "business_owner_approver_id": step9_data.get("business_owner_approver_id"),
        "final_approver_id": step9_data.get("final_approver_id"),
        "legal_compliance_reviewer_id": step9_data.get("legal_compliance_reviewer_id"),
        "security_reviewer_id": step9_data.get("security_reviewer_id"),
        "generated_content": generated,
        "quality_metrics": quality_metrics,
        "hallucination_layers": hallucination_layers,
        "prohibited_clause_flags": [],
        "has_unresolved_prohibited_clauses": False,
        "created_at": now,
        "updated_at": now,
    }

    result = await col_sow.insert_one(sow_doc)
    sow_id = str(result.inserted_id)

    # Update wizard status
    await col_wiz.update_one(
        {"_id": ObjectId(wizard_id)},
        {"$set": {
            "status": WizardStatus.generated,
            "sow_id": sow_id,
            "updated_at": now,
        }}
    )

    return {"sow_id": sow_id, "wizard_id": wizard_id, "quality_metrics": quality_metrics}


# ──────────────────────────────────────────────
# SOW ACTIONS
# ──────────────────────────────────────────────

async def get_sow(sow_id: str, user_id: str) -> Dict:
    col = get_sows_collection()
    try:
        obj_id = ObjectId(sow_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid SOW ID.")
    doc = await col.find_one({"_id": obj_id})
    if not doc:
        raise HTTPException(status_code=404, detail="SOW not found.")
    if doc.get("created_by_user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return _serialize(doc)


async def sow_action(sow_id: str, user_id: str, action: str, notes: Optional[str]) -> Dict:
    sow = await get_sow(sow_id, user_id)
    col = get_sows_collection()

    if action == "submit":
        # Check hard blocks
        layers = sow.get("hallucination_layers", [])
        red_layers = [l for l in layers if l.get("status") == "red"]
        if red_layers:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Submit blocked — red hallucination layers must be resolved.",
                    "red_layers": [l["name"] for l in red_layers]
                }
            )
        if sow.get("has_unresolved_prohibited_clauses"):
            raise HTTPException(status_code=422, detail="Submit blocked — unresolved prohibited clauses detected.")

        await col.update_one(
            {"_id": ObjectId(sow_id)},
            {"$set": {
                "status": SOWStatus.in_review,
                "submitted_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }}
        )
        return {"sow_id": sow_id, "status": "in_review", "message": "SOW submitted. Business Owner notified."}

    elif action == "request_changes":
        await col.update_one(
            {"_id": ObjectId(sow_id)},
            {"$set": {"status": SOWStatus.draft, "change_notes": notes, "updated_at": datetime.utcnow()}}
        )
        return {"sow_id": sow_id, "status": "draft", "message": "SOW returned to draft for changes."}

    elif action == "reject_regenerate":
        # Drop pipeline rows, delete SOW, point wizard back to Step 9 (no stored wizard_id field — use _id)
        await get_approvals_collection().delete_many({"sow_id": sow_id})
        await col.delete_one({"_id": ObjectId(sow_id)})
        wiz_col = get_wizards_collection()
        try:
            wiz_oid = ObjectId(sow["wizard_id"])
        except InvalidId as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid wizard reference on this SOW.",
            ) from exc
        await wiz_col.update_one(
            {"_id": wiz_oid},
            {
                "$set": {
                    "status": WizardStatus.completed,
                    "sow_id": None,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return {"sow_id": sow_id, "message": "SOW discarded. Wizard inputs preserved — return to Step 9 to regenerate."}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}. Use: submit | request_changes | reject_regenerate")
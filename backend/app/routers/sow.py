"""
SOW Review Router — AI Draft Review endpoints (§7.4)
"""

from fastapi import APIRouter, Depends, Path, Body
from typing import Optional

from app.core.security import get_current_user
from app.schemas.common import BaseResponse
from app.schemas.wizard import SOWActionRequest
from app.services import wizard_service

router = APIRouter(prefix="/sows", tags=["AI Draft Review"])


@router.get("/{sow_id}", response_model=BaseResponse,
            summary="Get full AI Draft Review — generated SOW with quality metrics")
async def get_sow(
    sow_id: str = Path(..., description="SOW ID returned from /generate"),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns the complete AI Draft Review payload (§7.4):

    **Quality Metrics Header:**
    - Overall Confidence (weighted average of per-section scores)
    - Risk Score /100 with level badge (Low / Medium / High / Critical)
    - Hallucination Flags count
    - Completeness percentage + status

    **Content:**
    - Generated SOW with per-section confidence badges
    - Hallucination Analysis — all 8 layers with detail
    - Risk Assessment breakdown (Completeness 30% + Confidence 25% + Compliance 25% + Pattern Match 20%)
    """
    sow = await wizard_service.get_sow(sow_id, current_user["id"])
    return BaseResponse(data=sow)


@router.get("/{sow_id}/hallucination-analysis", response_model=BaseResponse,
            summary="Get hallucination analysis — all 8 layer results")
async def get_hallucination_analysis(
    sow_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Returns detailed hallucination prevention layer analysis.

    **8 Layers:**
    1. Template Selection Validation
    2. Scope Boundary Enforcement
    3. Clause Library Matching (requires Data Sensitivity — no default)
    4. Cross-Step Consistency Check
    5. Compliance Alignment
    6. Prohibited Clause Detection (requires non-discrimination confirmation)
    7. Business Context Anchoring
    8. Evidence Pack Gate Validation

    Status: grey = inactive | green = passed | amber = warning | red = failed (blocks submission)
    """
    sow = await wizard_service.get_sow(sow_id, current_user["id"])
    layers = sow.get("hallucination_layers", [])
    red_layers = [l for l in layers if l.get("status") == "red"]
    return BaseResponse(data={
        "sow_id": sow_id,
        "layers": layers,
        "layers_active": sum(1 for l in layers if l.get("active")),
        "red_count": len(red_layers),
        "submission_blocked_by": [l["name"] for l in red_layers],
        "can_submit": len(red_layers) == 0 and not sow.get("has_unresolved_prohibited_clauses"),
    })


@router.get("/{sow_id}/risk-assessment", response_model=BaseResponse,
            summary="Get risk assessment breakdown")
async def get_risk_assessment(
    sow_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Returns weighted risk score breakdown:
    - Completeness: 30% weight
    - Confidence: 25% weight
    - Compliance: 25% weight
    - Pattern Match: 20% weight
    """
    sow = await wizard_service.get_sow(sow_id, current_user["id"])
    metrics = sow.get("quality_metrics", {})
    return BaseResponse(data={
        "sow_id": sow_id,
        "risk_score": metrics.get("risk_score"),
        "risk_level": metrics.get("risk_level"),
        "quality_metrics": metrics,
    })


@router.post("/{sow_id}/action", response_model=BaseResponse,
             summary="SOW action — submit | request_changes | reject_regenerate")
async def sow_action(
    sow_id: str,
    req: SOWActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    **Three available actions (§7.4.3):**

    - **submit**: Submits for approval. **HARD BLOCK** if any red hallucination layer OR unresolved prohibited clause.
      Approval route: Business Owner → GlimmoraTeam Commercial → Legal → Security → Final Approver.

    - **request_changes**: Opens edit mode. Returns SOW to draft for revisions.

    - **reject_regenerate**: Discards draft and returns to Step 9 with all 10 steps' inputs preserved.
    """
    result = await wizard_service.sow_action(sow_id, current_user["id"], req.action, req.change_notes)
    return BaseResponse(data=result)


@router.get("", response_model=BaseResponse, summary="List all SOWs for current user")
async def list_sows(current_user: dict = Depends(get_current_user)):
    from app.core.database import get_sows_collection
    col = get_sows_collection()
    cursor = col.find({"created_by_user_id": current_user["id"]}).sort("created_at", -1)
    results = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        results.append(doc)
    return BaseResponse(data=results)

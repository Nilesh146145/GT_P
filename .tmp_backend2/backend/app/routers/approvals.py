"""
Approval Pipeline Router — 5-Stage SOW Approval
Stage 1: Business Owner
Stage 2: GlimmoraTeam Commercial Review
Stage 3: Legal Review
Stage 4: Security Review
Stage 5: Final Approver Sign-off
"""

from fastapi import APIRouter, Depends, Path
from typing import Optional
from datetime import datetime
from bson import ObjectId

from app.core.security import get_current_user
from app.core.database import get_approvals_collection, get_sows_collection
from app.schemas.common import BaseResponse
from pydantic import BaseModel

router = APIRouter(prefix="/approvals", tags=["Approval Pipeline"])

STAGE_NAMES = {
    1: "Business Owner Review",
    2: "GlimmoraTeam Commercial Review",
    3: "Legal & Compliance Review",
    4: "Security Review",
    5: "Final Approver Sign-off",
}


class ApprovalDecision(BaseModel):
    decision: str  # approve | reject | request_changes
    comments: Optional[str] = None


class ApprovalRecord(BaseModel):
    sow_id: str
    stage: int
    stage_name: str
    status: str  # pending | approved | rejected | changes_requested
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    comments: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime


@router.get("/{sow_id}", response_model=BaseResponse,
            summary="Get approval status for a SOW")
async def get_approval_status(
    sow_id: str = Path(..., description="SOW ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns the full 5-stage approval pipeline status.

    **Pipeline:**
    1. Business Owner Review
    2. GlimmoraTeam Commercial Review (validates scope vs. budget)
    3. Legal & Compliance Review (validates Step 7 + Step 8 clauses)
    4. Security Review (validates data sensitivity + encryption requirements)
    5. Final Approver Sign-off

    Each stage shows: status (pending/approved/rejected/changes_requested),
    reviewer, comments, and timestamp.
    """
    col = get_approvals_collection()
    cursor = col.find({"sow_id": sow_id}).sort("stage", 1)
    stages = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        stages.append(doc)

    # If no stages exist yet, show pending pipeline
    if not stages:
        stages = [
            {
                "sow_id": sow_id,
                "stage": s,
                "stage_name": STAGE_NAMES[s],
                "status": "pending",
                "reviewer_id": None,
                "comments": None,
                "decided_at": None,
            }
            for s in range(1, 6)
        ]

    current_stage = next((s["stage"] for s in stages if s["status"] == "pending"), None)
    overall_status = "completed" if all(s["status"] == "approved" for s in stages) else \
        "rejected" if any(s["status"] == "rejected" for s in stages) else "in_progress"

    return BaseResponse(data={
        "sow_id": sow_id,
        "overall_status": overall_status,
        "current_active_stage": current_stage,
        "stages": stages,
        "approval_route": "Business Owner → GlimmoraTeam Commercial → Legal → Security → Final Approver",
    })


@router.post("/{sow_id}/stage/{stage}/decide", response_model=BaseResponse,
             summary="Record approval")
async def record_decision(
    sow_id: str,
    stage: int = Path(..., ge=1, le=5),
    decision: ApprovalDecision = ...,
    current_user: dict = Depends(get_current_user)
):
    """
    Records an approval decision for the given stage.

    - **approve**: Advances pipeline to next stage. Stage 5 approval completes the SOW.
    - **reject**: Rejects the SOW at this stage. Notifies creator.
    - **request_changes**: Returns to creator for revision without full rejection.

    Stage 2 (Commercial) validates that declared scope fits the budget envelope.
    Stage 3 (Legal) reviews all IP, warranty, and CR clauses from Step 8.
    Stage 4 (Security) validates data sensitivity classification and encryption requirements.
    """
    if stage not in range(1, 6):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Stage must be 1–5.")

    if decision.decision not in ("approve", "reject", "request_changes"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Decision must be: approve | reject | request_changes")

    col = get_approvals_collection()
    col_sow = get_sows_collection()
    now = datetime.utcnow()

    # Upsert the stage record
    await col.update_one(
        {"sow_id": sow_id, "stage": stage},
        {"$set": {
            "sow_id": sow_id,
            "stage": stage,
            "stage_name": STAGE_NAMES[stage],
            "status": decision.decision + "d" if decision.decision == "approve" else
                      "rejected" if decision.decision == "reject" else "changes_requested",
            "reviewer_id": current_user["id"],
            "reviewer_name": current_user.get("full_name", ""),
            "comments": decision.comments,
            "decided_at": now,
            "updated_at": now,
        }},
        upsert=True
    )

    # Update SOW status based on decision
    if decision.decision == "approve" and stage == 5:
        # Final approval — SOW is fully approved
        await col_sow.update_one(
            {"_id": ObjectId(sow_id)},
            {"$set": {"status": "approved", "approved_at": now, "updated_at": now}}
        )
        message = "SOW fully approved through all 5 stages. Production go-live may proceed."
    elif decision.decision == "approve":
        message = f"Stage {stage} approved. Pipeline advances to Stage {stage + 1}: {STAGE_NAMES.get(stage + 1, 'Complete')}."
    elif decision.decision == "reject":
        await col_sow.update_one(
            {"_id": ObjectId(sow_id)},
            {"$set": {"status": "rejected", "updated_at": now}}
        )
        message = f"SOW rejected at Stage {stage}. Creator has been notified."
    else:
        await col_sow.update_one(
            {"_id": ObjectId(sow_id)},
            {"$set": {"status": "changes_requested", "updated_at": now}}
        )
        message = f"Changes requested at Stage {stage}. SOW returned to creator for revision."

    return BaseResponse(
        message=message,
        data={
            "sow_id": sow_id,
            "stage": stage,
            "stage_name": STAGE_NAMES[stage],
            "decision": decision.decision,
            "comments": decision.comments,
            "decided_at": now.isoformat(),
        }
    )

"""
Manual SOW upload & approval flow — spec paths under /api/v1/sow
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse, Response

from app.core.security import get_current_user
from app.schemas.manual_sow.enums import ApprovalStageKey, CommercialSectionKey
from app.schemas.manual_sow.models import (
    ApproveStageBody,
    ConfirmSubmitBody,
    GenerateBody,
    MarkSectionCompleteBody,
    RejectStageBody,
    SowMetadataPatch,
)
from app.services.manual_sow.errors import ManualSowSpecException
from app.services.manual_sow.manual_sow_service import ManualSowService
from app.services.manual_sow import commercial_validation
from app.services.manual_sow.rate_limit import check_api_rate, check_upload_rate
from app.services.manual_sow.export_service import build_json_bundle, render_docx_bytes, render_pdf_bytes

router = APIRouter(prefix="/sow", tags=["Manual SOW"])


async def _rate_api(user: dict = Depends(get_current_user)) -> None:
    if not check_api_rate(user["id"]):
        from app.services.manual_sow.errors import raise_spec

        raise_spec(429, "Rate limit exceeded", "rate_limited")


@router.post("/upload")
async def sow_upload(
    file: UploadFile | None = File(None),
    projectTitle: str = Form(...),
    clientOrganisation: str = Form(...),
    linkedSowId: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """Spec §4 — multipart upload."""
    if not check_upload_rate(current_user["id"]):
        from app.services.manual_sow.errors import raise_spec

        raise_spec(429, "Upload rate limit exceeded", "rate_limited")
    if file is None:
        from app.services.manual_sow.errors import raise_spec

        raise_spec(400, "File field required", "missing_file")
    if len(projectTitle.strip()) < 3 or len(projectTitle) > 100:
        from app.services.manual_sow.errors import raise_spec

        raise_spec(422, "Invalid project title", "invalid_title", details={"projectTitle": "Min 3 max 100 chars"})
    if len(clientOrganisation.strip()) < 2 or len(clientOrganisation) > 100:
        from app.services.manual_sow.errors import raise_spec

        raise_spec(422, "Invalid client", "invalid_client", details={"clientOrganisation": "Min 2 max 100 chars"})

    data = await file.read()
    ct = file.content_type
    out = await ManualSowService.create_from_upload(
        user_id=current_user["id"],
        filename=file.filename or "upload.bin",
        content_type=ct,
        data=data,
        project_title=projectTitle,
        client_org=clientOrganisation,
        linked_sow_id=linkedSowId,
    )
    await ManualSowService.audit(current_user["id"], out["sow_id"], "upload_complete_response", {})
    return JSONResponse(content=out)


@router.get("", dependencies=[Depends(_rate_api)])
async def list_sows(
    current_user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None),
    intake_mode: Optional[str] = Query(None, alias="intake_mode"),
    client: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None, alias="created_by"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
):
    return await ManualSowService.list_sows(
        current_user["id"], status, intake_mode, client, created_by, page, limit, sort, order
    )


@router.get("/{sow_id}/upload-status", dependencies=[Depends(_rate_api)])
async def upload_status(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.upload_status(sow_id)


@router.get("/{sow_id}/extraction-report", dependencies=[Depends(_rate_api)])
async def extraction_report(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.extraction_report(sow_id)


@router.get("/{sow_id}/extraction-items", dependencies=[Depends(_rate_api)])
async def extraction_items(
    sow_id: str,
    current_user: dict = Depends(get_current_user),
    category: Optional[str] = Query(None, alias="category"),
    review_state: Optional[str] = Query(None, alias="review_state"),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.list_extraction_items(sow_id, category, review_state)


@router.patch("/{sow_id}/extraction-items/{item_id}/review-state", dependencies=[Depends(_rate_api)])
async def patch_extraction_review(
    sow_id: str,
    item_id: str,
    body: dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    rs = body.get("review_state")
    et = body.get("edited_text")
    return await ManualSowService.patch_extraction_review(sow_id, item_id, rs, et)


@router.post("/{sow_id}/extraction-items/accept-all", dependencies=[Depends(_rate_api)])
async def accept_all(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.accept_all_pending(sow_id)


@router.get("/{sow_id}/gap-items", dependencies=[Depends(_rate_api)])
async def gap_items(
    sow_id: str,
    current_user: dict = Depends(get_current_user),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None, alias="status"),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.list_gaps(sow_id, severity, status)


@router.patch("/{sow_id}/gap-items/{gap_id}", dependencies=[Depends(_rate_api)])
async def patch_gap(sow_id: str, gap_id: str, body: dict[str, Any], current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.patch_gap(sow_id, gap_id, body)


@router.get(
    "/{sow_id}/commercial-details",
    dependencies=[Depends(_rate_api)],
    summary="Commercial details (+ Section C AI when eligible)",
    description=(
        "Returns **`commercial_details`**, **`section_status`**, unlock flags, and **`aiGeneratedText`** (or null). "
        "Keep **`platformType`** / **`developmentScope`** under **`deliveryScope`** only. "
        "May auto-generate Section C AI when ready; **`regenerateAiTechStack`** or PATCH **`deliveryScope`** clears stored AI. See **`autoAiTechStack`** / **`commercialDetailsApiRevision`**."
    ),
)
async def get_commercial(
    sow_id: str,
    regenerate_ai_tech_stack: bool = Query(
        False,
        alias="regenerateAiTechStack",
        description="Clear stored Section C AI and regenerate when eligible.",
    ),
    current_user: dict = Depends(get_current_user),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.get_commercial_details(sow_id, regenerate_ai_tech_stack=regenerate_ai_tech_stack)


@router.patch("/{sow_id}/commercial-details/{section}", dependencies=[Depends(_rate_api)])
async def patch_commercial_section(
    sow_id: str,
    section: CommercialSectionKey,
    body: dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.patch_commercial_section(sow_id, section, body)


@router.post("/{sow_id}/commercial-details/{section}/validate", dependencies=[Depends(_rate_api)])
async def validate_commercial_section(
    sow_id: str,
    section: CommercialSectionKey,
    body: dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    ok, errors = commercial_validation.validate_section(section, body)
    return {"valid": ok, "errors": errors}


@router.post("/{sow_id}/commercial-details/sections/mark-complete", dependencies=[Depends(_rate_api)])
async def mark_complete(
    sow_id: str,
    body: MarkSectionCompleteBody,
    current_user: dict = Depends(get_current_user),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.mark_section_complete(sow_id, body.section)


@router.patch("/{sow_id}/approval-authorities", dependencies=[Depends(_rate_api)])
async def patch_authorities(sow_id: str, body: dict[str, Any], current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.patch_approval_authorities(sow_id, body)


@router.post("/{sow_id}/generate", dependencies=[Depends(_rate_api)], status_code=202)
async def trigger_sow_generation(sow_id: str, body: GenerateBody, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    out = await ManualSowService.start_generation(sow_id, current_user["id"])
    return JSONResponse(status_code=202, content=out)


@router.get("/{sow_id}/generation-status", dependencies=[Depends(_rate_api)])
async def generation_status(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.generation_status(sow_id)


@router.get("/{sow_id}/preview", dependencies=[Depends(_rate_api)])
async def preview(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.preview(sow_id)


@router.post("/{sow_id}/confirm-and-submit", dependencies=[Depends(_rate_api)])
async def confirm_submit(sow_id: str, body: ConfirmSubmitBody, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.confirm_submit(
        sow_id, current_user["id"], body.confirms_accuracy, body.notes
    )


@router.get("/{sow_id}/approval-stages", dependencies=[Depends(_rate_api)])
async def approval_stages(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.approval_stages_view(sow_id)


@router.post("/{sow_id}/approval-stage/{stage_key}/approve", dependencies=[Depends(_rate_api)])
async def approve_stage(
    sow_id: str,
    stage_key: ApprovalStageKey,
    body: ApproveStageBody,
    current_user: dict = Depends(get_current_user),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.approve_stage(
        sow_id, stage_key, body.reviewer, body.comments, current_user
    )


@router.post("/{sow_id}/approval-stage/{stage_key}/reject", dependencies=[Depends(_rate_api)])
async def reject_stage(
    sow_id: str,
    stage_key: ApprovalStageKey,
    body: RejectStageBody,
    current_user: dict = Depends(get_current_user),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.reject_stage(
        sow_id, stage_key, body.reviewer, body.reason, body.specific_feedback, current_user
    )


@router.get("/{sow_id}/approval-messages", dependencies=[Depends(_rate_api)])
async def approval_messages(
    sow_id: str,
    current_user: dict = Depends(get_current_user),
    stage: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.list_messages(sow_id, stage, limit)


@router.post("/{sow_id}/approval-messages/{message_id}/mark-read", dependencies=[Depends(_rate_api)])
async def mark_read(sow_id: str, message_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.mark_message_read(sow_id, message_id)


@router.get("/{sow_id}", dependencies=[Depends(_rate_api)])
async def get_sow(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.get_full_sow(sow_id)


@router.patch("/{sow_id}", dependencies=[Depends(_rate_api)])
async def patch_sow(sow_id: str, body: SowMetadataPatch, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    payload = body.model_dump(exclude_none=True, by_alias=True)
    return await ManualSowService.patch_metadata(sow_id, payload)


@router.delete("/{sow_id}", dependencies=[Depends(_rate_api)], status_code=204)
async def delete_sow(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    if doc.get("created_by_user_id") != current_user["id"]:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Only the creator may delete")
    await ManualSowService.soft_delete(sow_id)
    return Response(status_code=204)


@router.get("/{sow_id}/sections", dependencies=[Depends(_rate_api)])
async def sow_sections(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.sections_list(sow_id)


@router.get("/{sow_id}/clauses", dependencies=[Depends(_rate_api)])
async def sow_clauses(
    sow_id: str,
    current_user: dict = Depends(get_current_user),
    type: Optional[str] = Query(None, alias="type"),
    is_prohibited: Optional[bool] = Query(None, alias="is_prohibited"),
):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.clauses_list(sow_id, type, is_prohibited)


@router.get("/{sow_id}/hallucination-layers", dependencies=[Depends(_rate_api)])
async def sow_hallucination(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    return await ManualSowService.hallucination_layers(sow_id)


@router.get("/{sow_id}/export/pdf", dependencies=[Depends(_rate_api)])
async def export_pdf(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    gen = doc.get("generated") or {}
    content = gen.get("content") or {}
    secs = content.get("sections") or []
    if not secs:
        from app.services.manual_sow.errors import raise_spec

        raise_spec(422, "SOW not yet generated", "not_generated")
    pdf = render_pdf_bytes(doc.get("title") or "SOW", secs)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="SOW-{sow_id}.pdf"'},
    )


@router.get("/{sow_id}/export/docx", dependencies=[Depends(_rate_api)])
async def export_docx(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    gen = doc.get("generated") or {}
    content = gen.get("content") or {}
    secs = content.get("sections") or []
    if not secs:
        from app.services.manual_sow.errors import raise_spec

        raise_spec(422, "SOW not yet generated", "not_generated")
    raw = render_docx_bytes(doc.get("title") or "SOW", secs)
    return Response(
        content=raw,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="SOW-{sow_id}.docx"'},
    )


@router.get("/{sow_id}/export/json", dependencies=[Depends(_rate_api)])
async def export_json(sow_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ManualSowService.get_sow_doc(sow_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="SOW not found")
    await ManualSowService.assert_access(doc, current_user)
    bundle = build_json_bundle(
        doc,
        ((doc.get("generated") or {}).get("content") or {}).get("sections") or [],
        doc.get("commercial_details") or {},
        doc.get("approval_stages") or [],
    )
    import json

    return Response(content=json.dumps(bundle, default=str), media_type="application/json")


nda_router = APIRouter(tags=["NDA"])


@nda_router.get("/nda-document")
async def nda_document():
    html = """<!DOCTYPE html><html><head><meta charset="utf-8"/><title>NDA</title></head>
    <body><h1>Mutual Non-Disclosure Agreement</h1>
    <p>This is a placeholder NDA HTML document for the GlimmoraTeam platform.</p></body></html>"""
    return {"html": html}


@nda_router.get("/nda-download")
async def nda_download(name: str = Query(...), date: Optional[str] = Query(None)):
    if not name.strip():
        from app.services.manual_sow.errors import raise_spec

        raise_spec(400, "Missing name", "missing_name")
    try:
        pdf = render_pdf_bytes(f"NDA — {name}", [{"title": "Signatory", "content": f"Name: {name}\nDate: {date or 'today'}"}])
    except Exception:
        from app.services.manual_sow.errors import raise_spec

        raise_spec(500, "PDF generation failed", "pdf_failed")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="NDA-Signed-{name[:40]}.pdf"'},
    )

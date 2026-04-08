"""
Manual SOW intake — persistence and business logic (MongoDB).
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.database import (
    get_manual_sow_approval_messages_collection,
    get_manual_sow_audit_log_collection,
    get_manual_sow_extraction_items_collection,
    get_manual_sow_files_collection,
    get_manual_sow_gap_items_collection,
    get_manual_sows_collection,
)
from app.schemas.manual_sow.enums import (
    ApprovalStageKey,
    ApprovalStageStatus,
    CommercialSectionKey,
    CommercialSectionStatus,
    ManualSowStatus,
    STAGE_ORDER,
    STAGE_SLA_DAYS,
    UploadProcessingState,
)
from app.services.manual_sow import extraction_service, gap_analysis, storage
from app.services.manual_sow.commercial_prefill import (
    build_commercial_prefill_from_extraction,
    commercial_needs_prefill,
    merge_commercial_details_prefill,
)
from app.services.manual_sow.errors import raise_spec
from app.services.manual_sow.commercial_validation import (
    all_sections_complete,
    validate_approvers,
    validate_section,
)
from app.services.manual_sow.gates import gate_step3_to_4, gate_step4_to_5, gate_step5_to_6
from app.services.manual_sow.wizard_shape_adapter import build_wizard_data_from_manual, steps_completed_for_manual
from app.services.confidence import compute_confidence
from app.services.sow_generator import compute_risk_score, generate_sow_content, run_hallucination_checks


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_file_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def map_layer_status(status: str) -> str:
    return {"green": "passed", "amber": "warning", "red": "failed", "grey": "skipped"}.get(status, "skipped")


def _normalize_email(s: str) -> str:
    return (s or "").strip().lower()


def reviewer_email_for_stage(auth: Dict[str, Any], stage: ApprovalStageKey) -> str:
    """Resolve reviewer email; optional stages fall back to final approver when unset."""
    a = auth or {}
    final = a.get("final_approver")
    m = {
        ApprovalStageKey.business: a.get("business_owner_approver"),
        ApprovalStageKey.glimmora_commercial: a.get("glimmora_commercial_approver")
        or a.get("commercial_approver")
        or final,
        ApprovalStageKey.legal: a.get("legal_reviewer") or final,
        ApprovalStageKey.security: a.get("security_reviewer") or final,
        ApprovalStageKey.final: final,
    }
    return _normalize_email(m.get(stage) or "")


class ManualSowService:
    @staticmethod
    async def audit(user_id: str, sow_public_id: str, action: str, meta: Optional[Dict] = None) -> None:
        col = get_manual_sow_audit_log_collection()
        await col.insert_one(
            {
                "created_at": _utcnow(),
                "user_id": user_id,
                "sow_public_id": sow_public_id,
                "action": action,
                "meta": meta or {},
            }
        )

    @staticmethod
    async def get_sow_doc(public_id: str) -> Optional[Dict[str, Any]]:
        col = get_manual_sows_collection()
        return await col.find_one({"public_id": public_id, "deleted_at": None})

    @staticmethod
    async def assert_access(doc: Dict[str, Any], user: Dict[str, Any], need_write: bool = False) -> None:
        from fastapi import HTTPException

        uid = user.get("id")
        email = _normalize_email(user.get("email") or "")
        if doc.get("created_by_user_id") == uid:
            return
        auth = doc.get("approval_authorities") or {}
        emails = {_normalize_email(v) for v in auth.values() if isinstance(v, str) and v.strip()}
        if email and email in emails:
            return
        raise HTTPException(status_code=404, detail="SOW not found.")

    @staticmethod
    async def duplicate_hash_exists(user_id: str, digest: str) -> bool:
        col = get_manual_sow_files_collection()
        since = _utcnow() - timedelta(days=settings.MANUAL_SOW_DUPLICATE_HASH_DAYS)
        found = await col.find_one(
            {
                "created_by_user_id": user_id,
                "hash_sha256": digest,
                "uploaded_at": {"$gte": since},
            }
        )
        return found is not None

    @staticmethod
    async def validate_upload_file(
        filename: str,
        content_type: Optional[str],
        data: bytes,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Returns (error_code, message) or (None, None) if OK."""
        n = len(data)
        if n > settings.MANUAL_SOW_MAX_UPLOAD_BYTES:
            return "file_too_large", "File exceeds 50 MB limit"
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        allowed_ext = {"pdf", "docx", "doc"}
        if ext not in allowed_ext:
            return "unsupported_format", "Only PDF, DOCX, DOC are accepted"
        ct = (content_type or "").lower()
        ok_ct = any(
            x in ct
            for x in (
                "pdf",
                "msword",
                "wordprocessingml",
            )
        )
        if content_type and not ok_ct and ext not in allowed_ext:
            return "unsupported_format", "Invalid MIME type"

        if ext == "pdf" and data:
            try:
                from pypdf import PdfReader
                import io

                r = PdfReader(io.BytesIO(data))
                if r.is_encrypted:
                    return "password_protected", "PDF is password-protected"
            except Exception:
                pass

        if settings.MANUAL_SOW_AV_SCAN_ENABLED:
            return "malware_detected", "Antivirus scan failed"

        return None, None

    @staticmethod
    async def create_from_upload(
        *,
        user_id: str,
        filename: str,
        content_type: Optional[str],
        data: bytes,
        project_title: str,
        client_org: str,
        linked_sow_id: Optional[str],
    ) -> Dict[str, Any]:
        err, msg = await ManualSowService.validate_upload_file(filename, content_type, data)
        if err:
            code_map = {
                "file_too_large": 413,
                "unsupported_format": 400,
                "password_protected": 400,
                "malware_detected": 400,
            }
            raise_spec(code_map.get(err, 400), msg or err, err)

        digest = hashlib.sha256(data).hexdigest()
        if await ManualSowService.duplicate_hash_exists(user_id, digest):
            raise_spec(409, "Duplicate file uploaded within 30 days", "duplicate_file")

        public_id = str(uuid.uuid4())
        storage_key, size_b = storage.save_upload(public_id, filename, data)
        now = _utcnow()

        col_sow = get_manual_sows_collection()
        col_files = get_manual_sow_files_collection()

        section_status = {k.value: "not_started" for k in CommercialSectionKey}
        doc = {
            "public_id": public_id,
            "title": project_title.strip(),
            "client": client_org.strip(),
            "status": ManualSowStatus.parsing.value,
            "intake_mode": "manual_upload",
            "confidentiality": "internal",
            "data_sensitivity": "internal",
            "version": 1,
            "created_by_user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "linked_sow_public_id": linked_sow_id,
            "commercial_details": {},
            "section_status": section_status,
            "approval_authorities": {},
            "upload_processing": {
                "state": UploadProcessingState.uploading.value,
                "progress_percent": 5,
                "current_stage_label": "Storing file",
                "started_at": now,
                "estimated_completion": None,
                "error_message": None,
            },
            "extraction_report": None,
            "generated": None,
            "generation_job": None,
            "approval_stages": [],
            "change_requests": [],
            "tags": [],
            "stakeholders": [],
            "deleted_at": None,
        }
        await col_sow.insert_one(doc)

        await col_files.insert_one(
            {
                "public_id": str(uuid.uuid4()),
                "sow_public_id": public_id,
                "storage_key": storage_key,
                "original_name": filename,
                "mime_type": content_type or "application/octet-stream",
                "size_bytes": size_b,
                "hash_sha256": digest,
                "created_by_user_id": user_id,
                "uploaded_at": now,
            }
        )

        await ManualSowService.audit(user_id, public_id, "upload", {"filename": filename, "bytes": size_b})

        asyncio.create_task(ManualSowService._run_extraction_job(public_id, storage_key, filename))

        pages = 1
        return {
            "sow_id": public_id,
            "status": ManualSowStatus.parsing.value,
            "intake_mode": "manual_upload",
            "title": doc["title"],
            "client": doc["client"],
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "file_size": _format_file_size(size_b),
            "pages": pages,
            "uploaded_file": {
                "name": filename,
                "size": size_b,
                "type": content_type or "application/octet-stream",
                "uploaded_at": now.isoformat().replace("+00:00", "Z"),
            },
        }

    @staticmethod
    async def _run_extraction_job(sow_public_id: str, storage_key: str, filename: str) -> None:
        col = get_manual_sows_collection()
        col_items = get_manual_sow_extraction_items_collection()
        states = [
            (UploadProcessingState.extracting.value, 25, "Extracting"),
            (UploadProcessingState.analyzing.value, 45, "Analyzing structure"),
            (UploadProcessingState.detecting.value, 65, "Detecting clauses"),
            (UploadProcessingState.scoring.value, 85, "Scoring confidence"),
        ]
        try:
            raw = storage.read_file(storage_key)
            for st, pct, label in states:
                await col.update_one(
                    {"public_id": sow_public_id},
                    {
                        "$set": {
                            "upload_processing.state": st,
                            "upload_processing.progress_percent": pct,
                            "upload_processing.current_stage_label": label,
                            "updated_at": _utcnow(),
                        }
                    },
                )
                await asyncio.sleep(0.05)

            result = extraction_service.extract_bytes(filename, raw)

            doc_pre = await col.find_one({"public_id": sow_public_id}) or {}
            merged_cd = dict(doc_pre.get("commercial_details") or {})
            sec_stat = dict(doc_pre.get("section_status") or {})
            if doc_pre.get("public_id"):
                seed_bc, seed_ti = build_commercial_prefill_from_extraction(
                    result.items,
                    result.report,
                    title=str(doc_pre.get("title") or ""),
                    client=str(doc_pre.get("client") or ""),
                )
                merged_cd = merge_commercial_details_prefill(merged_cd, seed_bc, seed_ti)
                for sec_key in (CommercialSectionKey.businessContext.value, CommercialSectionKey.techIntegrations.value):
                    if sec_stat.get(sec_key) == CommercialSectionStatus.not_started.value:
                        sec_stat[sec_key] = CommercialSectionStatus.in_progress.value

            now_done = _utcnow()
            await col.update_one(
                {"public_id": sow_public_id},
                {
                    "$set": {
                        "upload_processing.state": UploadProcessingState.complete.value,
                        "upload_processing.progress_percent": 100,
                        "upload_processing.current_stage_label": "Complete",
                        "extraction_report": result.report,
                        "parsed_sections": len(result.items),
                        "total_sections": len(result.items),
                        "pages": result.page_count,
                        "status": ManualSowStatus.review.value,
                        "commercial_details": merged_cd,
                        "section_status": sec_stat,
                        "updated_at": now_done,
                    }
                },
            )
            for it in result.items:
                it["sow_public_id"] = sow_public_id
                await col_items.insert_one(it)
        except Exception as e:
            await col.update_one(
                {"public_id": sow_public_id},
                {
                    "$set": {
                        "upload_processing.state": UploadProcessingState.error.value,
                        "upload_processing.error_message": str(e),
                        "updated_at": _utcnow(),
                    }
                },
            )

    @staticmethod
    async def upload_status(public_id: str) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        up = doc.get("upload_processing") or {}
        return {
            "sow_id": public_id,
            "processing_state": up.get("state", "idle"),
            "progress_percent": up.get("progress_percent", 0),
            "current_stage_label": up.get("current_stage_label", ""),
            "started_at": (up.get("started_at") or _utcnow()).isoformat().replace("+00:00", "Z"),
            "estimated_completion": (
                up.get("estimated_completion").isoformat().replace("+00:00", "Z")
                if up.get("estimated_completion")
                else None
            ),
        }

    @staticmethod
    async def extraction_report(public_id: str) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        if (doc.get("upload_processing") or {}).get("state") != UploadProcessingState.complete.value:
            raise_spec(409, "Extraction not complete", "extraction_incomplete")
        rep = doc.get("extraction_report") or {}
        return {"sow_id": public_id, "report": rep}

    @staticmethod
    async def list_extraction_items(
        public_id: str, category: Optional[str], review_state: Optional[str]
    ) -> Dict[str, Any]:
        col = get_manual_sow_extraction_items_collection()
        q: Dict[str, Any] = {"sow_public_id": public_id}
        if category:
            q["category"] = category
        if review_state:
            q["review_state"] = review_state
        items: List[Dict[str, Any]] = []
        stats = {"total": 0, "pending": 0, "accepted": 0, "edited": 0, "excluded": 0}
        async for it in col.find(q):
            stats["total"] += 1
            st = it.get("review_state", "pending")
            if st in stats:
                stats[st] += 1
            items.append(
                {
                    "id": it["public_id"],
                    "category": it["category"],
                    "text": it["text"],
                    "source_page_number": it["source_page_number"],
                    "source_highlight": it["source_highlight"],
                    "review_state": it["review_state"],
                    "edited_text": it.get("edited_text"),
                    "confidence": it.get("confidence", 0),
                }
            )
        return {"sow_id": public_id, "items": items, "stats": stats}

    @staticmethod
    async def patch_extraction_review(
        sow_public_id: str, item_public_id: str, review_state: str, edited_text: Optional[str]
    ) -> Dict[str, Any]:
        col = get_manual_sow_extraction_items_collection()
        it = await col.find_one({"sow_public_id": sow_public_id, "public_id": item_public_id})
        if not it:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Item not found")
        if review_state == "edited" and not (edited_text and edited_text.strip()):
            raise_spec(400, "edited_text required when review_state is edited", "invalid_state_transition")
        await col.update_one(
            {"_id": it["_id"]},
            {
                "$set": {
                    "review_state": review_state,
                    "edited_text": edited_text if review_state == "edited" else None,
                }
            },
        )
        return {"id": item_public_id, "review_state": review_state, "edited_text": edited_text}

    @staticmethod
    async def accept_all_pending(sow_public_id: str) -> Dict[str, Any]:
        col = get_manual_sow_extraction_items_collection()
        now = _utcnow()
        result = await col.update_many(
            {"sow_public_id": sow_public_id, "review_state": "pending"},
            {"$set": {"review_state": "accepted"}},
        )
        return {
            "sow_id": sow_public_id,
            "accepted_count": result.modified_count,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    async def ensure_gap_items(sow_public_id: str) -> None:
        col_g = get_manual_sow_gap_items_collection()
        existing = await col_g.count_documents({"sow_public_id": sow_public_id})
        if existing > 0:
            return
        col_i = get_manual_sow_extraction_items_collection()
        items: List[Dict[str, Any]] = []
        async for it in col_i.find({"sow_public_id": sow_public_id}):
            items.append(it)
        for g in gap_analysis.build_gap_items(items):
            g["sow_public_id"] = sow_public_id
            await col_g.insert_one(g)

    @staticmethod
    async def list_gaps(
        sow_public_id: str, severity: Optional[str], status_filter: Optional[str]
    ) -> Dict[str, Any]:
        await ManualSowService.ensure_gap_items(sow_public_id)
        col = get_manual_sow_gap_items_collection()
        q: Dict[str, Any] = {"sow_public_id": sow_public_id}
        if severity:
            q["severity"] = severity
        gaps: List[Dict[str, Any]] = []
        summary = {"critical": 0, "important": 0, "optional": 0, "prohibited": 0}
        async for g in col.find(q):
            sev = g.get("severity") or "optional"
            if sev in summary and sev != "prohibited":
                summary[sev] = summary.get(sev, 0) + 1
            if g.get("is_prohibited"):
                summary["prohibited"] += 1

            if status_filter:
                ok = False
                if status_filter == "unresolved" and not g.get("is_resolved"):
                    ok = True
                elif status_filter == "resolved" and g.get("is_resolved"):
                    ok = True
                elif status_filter == "acknowledged" and g.get("is_acknowledged"):
                    ok = True
                elif status_filter == "dismissed" and g.get("is_dismissed"):
                    ok = True
                elif status_filter == "prohibited" and g.get("is_prohibited"):
                    ok = True
                if not ok:
                    continue

            gaps.append(
                {
                    "id": g["public_id"],
                    "severity": g["severity"],
                    "title": g["title"],
                    "description": g["description"],
                    "section": g["section"],
                    "is_resolved": g.get("is_resolved", False),
                    "is_acknowledged": g.get("is_acknowledged", False),
                    "is_dismissed": g.get("is_dismissed", False),
                    "is_prohibited": g.get("is_prohibited", False),
                    "remediation_suggestions": g.get("remediation_suggestions") or [],
                }
            )
        return {"sow_id": sow_public_id, "gaps": gaps, "summary": summary}

    @staticmethod
    async def patch_gap(
        sow_public_id: str, gap_public_id: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        col = get_manual_sow_gap_items_collection()
        g = await col.find_one({"sow_public_id": sow_public_id, "public_id": gap_public_id})
        if not g:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Gap not found")
        if body.get("is_dismissed") and g.get("severity") in ("critical", "important"):
            raise_spec(400, "Cannot dismiss critical or important gap", "invalid_gap_action")
        updates: Dict[str, Any] = {}
        for k in ("is_resolved", "is_acknowledged", "is_dismissed"):
            if k in body and body[k] is not None:
                updates[k] = body[k]
        if body.get("remediation_suggestions") is not None:
            updates["remediation_suggestions"] = body["remediation_suggestions"]
        now = _utcnow()
        updates["updated_at"] = now
        await col.update_one({"_id": g["_id"]}, {"$set": updates})
        merged = {**g, **updates}
        return {
            "id": gap_public_id,
            "is_resolved": merged.get("is_resolved", False),
            "is_acknowledged": merged.get("is_acknowledged", False),
            "is_dismissed": merged.get("is_dismissed", False),
            "updated_at": now.isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    async def _ensure_commercial_prefill_from_extraction(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gap-fill businessContext and techIntegrations from stored extraction items (legacy rows or race with GET).
        """
        up = doc.get("upload_processing") or {}
        if up.get("state") != UploadProcessingState.complete.value:
            return doc
        if not commercial_needs_prefill(doc.get("commercial_details")):
            return doc
        col_i = get_manual_sow_extraction_items_collection()
        items: List[Dict[str, Any]] = []
        async for it in col_i.find({"sow_public_id": doc["public_id"]}):
            row = dict(it)
            row.pop("_id", None)
            items.append(row)
        if not items:
            return doc
        seed_bc, seed_ti = build_commercial_prefill_from_extraction(
            items,
            doc.get("extraction_report") or {},
            title=str(doc.get("title") or ""),
            client=str(doc.get("client") or ""),
        )
        merged = merge_commercial_details_prefill(doc.get("commercial_details") or {}, seed_bc, seed_ti)
        if merged == doc.get("commercial_details"):
            return doc
        sec_stat = dict(doc.get("section_status") or {})
        for sec_key in (CommercialSectionKey.businessContext.value, CommercialSectionKey.techIntegrations.value):
            if sec_stat.get(sec_key) == CommercialSectionStatus.not_started.value:
                sec_stat[sec_key] = CommercialSectionStatus.in_progress.value
        now = _utcnow()
        col = get_manual_sows_collection()
        await col.update_one(
            {"public_id": doc["public_id"]},
            {"$set": {"commercial_details": merged, "section_status": sec_stat, "updated_at": now}},
        )
        out = dict(doc)
        out["commercial_details"] = merged
        out["section_status"] = sec_stat
        return out

    @staticmethod
    async def get_commercial_details(public_id: str) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        doc = await ManualSowService._ensure_commercial_prefill_from_extraction(doc)
        return {
            "sow_id": public_id,
            "commercial_details": doc.get("commercial_details") or {},
            "section_status": doc.get("section_status") or {},
            "approval_authorities": doc.get("approval_authorities") or {},
        }

    @staticmethod
    async def patch_commercial_section(public_id: str, section: CommercialSectionKey, data: Dict[str, Any]) -> Dict[str, Any]:
        col = get_manual_sows_collection()
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        # Product request: commercialLegal no longer accepts warranty/final-approver fields.
        if section == CommercialSectionKey.commercialLegal:
            sanitized = dict(data or {})
            for key in ("warrantyPeriod", "warranty_period", "finalApprover", "final_approver"):
                sanitized.pop(key, None)
            data = sanitized
        cd = dict(doc.get("commercial_details") or {})
        cd[section.value] = {**(cd.get(section.value) or {}), **data}
        sec_stat = dict(doc.get("section_status") or {})
        sec_stat[section.value] = "in_progress"
        now = _utcnow()
        await col.update_one(
            {"public_id": public_id},
            {"$set": {"commercial_details": cd, "section_status": sec_stat, "updated_at": now}},
        )
        return {"section": section.value, "status": "in_progress", "updated_at": now.isoformat().replace("+00:00", "Z")}

    @staticmethod
    async def mark_section_complete(public_id: str, section: CommercialSectionKey) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        data = (doc.get("commercial_details") or {}).get(section.value) or {}
        ok, errors = validate_section(section, data)
        if not ok:
            raise_spec(400, "Validation failed", "validation_error", details=errors)
        col = get_manual_sows_collection()
        sec_stat = dict(doc.get("section_status") or {})
        sec_stat[section.value] = "complete"
        now = _utcnow()
        await col.update_one(
            {"public_id": public_id},
            {"$set": {"section_status": sec_stat, "updated_at": now}},
        )
        return {
            "section": section.value,
            "status": "complete",
            "completed_at": now.isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    async def patch_approval_authorities(public_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        prev = (doc or {}).get("approval_authorities") or {}
        auth = {
            **prev,
            "sow_submitter": body.get("sow_submitter", prev.get("sow_submitter")),
            "business_owner_approver": body.get("business_owner_approver", prev.get("business_owner_approver")),
            "final_approver": body.get("final_approver", prev.get("final_approver")),
            "legal_reviewer": body.get("legal_reviewer", prev.get("legal_reviewer")),
            "security_reviewer": body.get("security_reviewer", prev.get("security_reviewer")),
            "glimmora_commercial_approver": body.get(
                "glimmora_commercial_approver", prev.get("glimmora_commercial_approver")
            ),
        }
        ok, errors = validate_approvers(auth)
        if not ok:
            raise_spec(400, "Missing required approvers", "missing_approvers", details=errors)
        col = get_manual_sows_collection()
        now = _utcnow()
        await col.update_one(
            {"public_id": public_id},
            {"$set": {"approval_authorities": auth, "updated_at": now}},
        )
        return {
            "business_owner_approver": auth["business_owner_approver"],
            "final_approver": auth["final_approver"],
            "updated_at": now.isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    async def start_generation(public_id: str, user_id: str) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        col_i = get_manual_sow_extraction_items_collection()
        items: List[Dict[str, Any]] = []
        async for it in col_i.find({"sow_public_id": public_id}):
            items.append(it)
        if not gate_step3_to_4(items):
            raise_spec(422, "At least one features item must be accepted or edited", "precondition_failed")
        col_g = get_manual_sow_gap_items_collection()
        gaps: List[Dict[str, Any]] = []
        async for g in col_g.find({"sow_public_id": public_id}):
            gaps.append(g)
        if gaps and not gate_step4_to_5(gaps):
            raise_spec(422, "Resolve or acknowledge all critical and important gaps", "precondition_failed")
        if not gate_step5_to_6(doc.get("section_status") or {}, doc.get("approval_authorities") or {}):
            raise_spec(422, "All commercial sections must be complete and approvers set", "precondition_failed")

        job = doc.get("generation_job") or {}
        if job.get("status") == "generating":
            raise_spec(409, "Generation already in progress", "generation_in_progress")

        col = get_manual_sows_collection()
        now = _utcnow()
        await col.update_one(
            {"public_id": public_id},
            {
                "$set": {
                    "generation_job": {
                        "status": "generating",
                        "progress_percent": 0,
                        "started_at": now,
                        "completed_at": None,
                        "error_message": None,
                    },
                    "updated_at": now,
                }
            },
        )
        asyncio.create_task(ManualSowService._run_generation_job(public_id))
        await ManualSowService.audit(user_id, public_id, "generation_started", {})
        return {
            "sow_id": public_id,
            "status": "generating",
            "started_at": now.isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    async def _run_generation_job(public_id: str) -> None:
        col = get_manual_sows_collection()
        col_i = get_manual_sow_extraction_items_collection()
        try:
            doc = await col.find_one({"public_id": public_id})
            if not doc:
                return
            feature_texts: List[str] = []
            async for it in col_i.find({"sow_public_id": public_id, "category": "features"}):
                if it.get("review_state") in ("accepted", "edited"):
                    t = it.get("edited_text") if it.get("review_state") == "edited" else it.get("text")
                    if t:
                        feature_texts.append(t)
            wizard_data = build_wizard_data_from_manual(
                title=doc["title"],
                client=doc["client"],
                commercial_details=doc.get("commercial_details") or {},
                feature_module_texts=feature_texts,
            )
            steps_done = steps_completed_for_manual()
            generated = generate_sow_content(wizard_data)
            layers_raw = run_hallucination_checks(wizard_data, steps_done)
            risk = compute_risk_score(wizard_data)
            conf = compute_confidence(wizard_data, [])
            layers_api = [
                {
                    "layer": L["layer_id"],
                    "name": L["name"],
                    "status": map_layer_status(L.get("status", "grey")),
                    "details": L.get("detail", ""),
                }
                for L in layers_raw
            ]
            preview_text = ""
            for s in generated.get("sections", [])[:2]:
                preview_text += s.get("content", "")[:250]
            preview_text = preview_text[:500]
            now = _utcnow()
            await col.update_one(
                {"public_id": public_id},
                {
                    "$set": {
                        "generated": {
                            "wizard_shaped": wizard_data,
                            "content": generated,
                            "hallucination_layers_raw": layers_raw,
                            "risk": risk,
                            "confidence": conf,
                            "preview_text": preview_text,
                            "completed_at": now,
                        },
                        "generation_job": {
                            "status": "complete",
                            "progress_percent": 100,
                            "started_at": (doc.get("generation_job") or {}).get("started_at", now),
                            "completed_at": now,
                            "error_message": None,
                            "generated_sections": len(generated.get("sections", [])),
                        },
                        "ai_confidence": conf.get("overall", 0),
                        "risk_score": {
                            "completeness": risk["breakdown"]["completeness"],
                            "confidence": int(conf.get("overall", 0)),
                            "compliance": risk["breakdown"]["compliance"],
                            "pattern_match": risk["breakdown"]["pattern_match"],
                            "overall": int(100 - risk.get("risk_score", 50)),
                        },
                        "hallucination_flags": [],
                        "updated_at": now,
                    }
                },
            )
        except Exception as e:
            await col.update_one(
                {"public_id": public_id},
                {
                    "$set": {
                        "generation_job": {
                            "status": "error",
                            "progress_percent": 0,
                            "error_message": str(e),
                        },
                        "updated_at": _utcnow(),
                    }
                },
            )

    @staticmethod
    async def generation_status(public_id: str) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        job = doc.get("generation_job") or {}
        gen = doc.get("generated") or {}
        out: Dict[str, Any] = {
            "sow_id": public_id,
            "status": job.get("status", "idle"),
            "progress_percent": job.get("progress_percent", 0),
            "generated_sections": job.get("generated_sections", len((gen.get("content") or {}).get("sections", []))),
            "completed_at": (
                job.get("completed_at").isoformat().replace("+00:00", "Z") if job.get("completed_at") else None
            ),
        }
        if job.get("status") == "error" and job.get("error_message"):
            out["error_message"] = job["error_message"]
        return out

    @staticmethod
    async def preview(public_id: str) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        gen = doc.get("generated") or {}
        if not gen:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Not generated")
        job = doc.get("generation_job") or {}
        layers = []
        for L in (gen.get("hallucination_layers_raw") or []):
            layers.append(
                {
                    "layer": L["layer_id"],
                    "name": L["name"],
                    "status": map_layer_status(L.get("status", "grey")),
                    "details": L.get("detail", ""),
                }
            )
        hard_blocks: List[str] = []
        completed = gen.get("completed_at")
        stale = False
        if completed:
            if isinstance(completed, str):
                completed = datetime.fromisoformat(completed.replace("Z", "+00:00"))
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            stale = _utcnow() - completed > timedelta(days=settings.MANUAL_SOW_STALE_GENERATION_DAYS)
        if stale:
            hard_blocks.append("stale_document")
        for L in gen.get("hallucination_layers_raw") or []:
            if L.get("status") == "red":
                hard_blocks.append(f"layer_{L.get('layer_id')}_failed")

        risk = gen.get("risk") or {}
        conf = gen.get("confidence") or {}
        return {
            "sow_id": public_id,
            "quality_metrics": {
                "confidence": int(conf.get("overall", 0)),
                "risk_score": int(risk.get("risk_score", 0)),
                "hallucination_flags": sum(1 for L in (gen.get("hallucination_layers_raw") or []) if L.get("status") == "red"),
                "completeness": int(risk.get("breakdown", {}).get("completeness", 0)),
            },
            "is_stale_document": stale,
            "hard_blocks": hard_blocks,
            "preview_text": gen.get("preview_text", ""),
            "export_formats": ["pdf", "docx"],
        }

    @staticmethod
    async def confirm_submit(public_id: str, user_id: str, confirms: bool, notes: Optional[str]) -> Dict[str, Any]:
        if not confirms:
            raise_spec(400, "confirms_accuracy must be true", "confirmation_required")
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        job = doc.get("generation_job") or {}
        if job.get("status") != "complete":
            raise_spec(422, "Generation not complete", "not_ready")
        prev = await ManualSowService.preview(public_id)
        if prev.get("hard_blocks"):
            raise_spec(
                409,
                "Hard blocks present — cannot submit",
                "hard_blocks",
                details={b: b for b in prev["hard_blocks"]},
            )
        now = _utcnow()
        stages = []
        for i, sk in enumerate(STAGE_ORDER):
            st = ApprovalStageStatus.in_review.value if i == 0 else ApprovalStageStatus.pending.value
            stages.append(
                {
                    "stage": sk.value,
                    "status": st,
                    "reviewer": None,
                    "reviewed_at": None,
                    "comments": None,
                    "sla_status": "on_track",
                    "sla_due_days": STAGE_SLA_DAYS.get(sk.value, 3),
                }
            )
        col = get_manual_sows_collection()
        await col.update_one(
            {"public_id": public_id},
            {
                "$set": {
                    "status": ManualSowStatus.approval.value,
                    "approval_stages": stages,
                    "submitted_at": now,
                    "submission_notes": notes,
                    "updated_at": now,
                }
            },
        )
        await ManualSowService._append_message(
            public_id,
            0,
            ApprovalStageKey.business.value,
            "stage_activated",
            "Platform",
            "System",
            doc.get("approval_authorities", {}).get("business_owner_approver", "Reviewer"),
            "Business Owner",
            "SOW submitted for business review",
            notes or "Please review the submitted SOW.",
        )
        await ManualSowService.audit(user_id, public_id, "submitted_for_approval", {})
        return {
            "sow_id": public_id,
            "status": ManualSowStatus.approval.value,
            "submitted_at": now.isoformat().replace("+00:00", "Z"),
            "approval_pipeline": {"current_stage": 1, "stages": [{"stage": s["stage"], "status": s["status"]} for s in stages]},
        }

    @staticmethod
    async def _append_message(
        sow_public_id: str,
        stage_index: int,
        stage_key: str,
        msg_type: str,
        sender_role: str,
        sender_name: str,
        recipient_name: str,
        recipient_role: str,
        subject: str,
        body: str,
    ) -> None:
        col = get_manual_sow_approval_messages_collection()
        mid = str(uuid.uuid4())
        now = _utcnow()
        await col.insert_one(
            {
                "public_id": mid,
                "sow_public_id": sow_public_id,
                "stage_index": stage_index,
                "stage_key": stage_key,
                "type": msg_type,
                "sender_name": sender_name,
                "sender_role": sender_role,
                "recipient_name": recipient_name,
                "recipient_role": recipient_role,
                "subject": subject,
                "body": body,
                "sent_at": now,
                "read": False,
            }
        )

    @staticmethod
    async def approval_stages_view(public_id: str) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        stages = doc.get("approval_stages") or []
        out = []
        for s in stages:
            out.append(
                {
                    "stage": s["stage"],
                    "status": s["status"],
                    "reviewer": s.get("reviewer"),
                    "reviewed_at": s.get("reviewed_at").isoformat().replace("+00:00", "Z") if s.get("reviewed_at") else None,
                    "comments": s.get("comments"),
                    "sla_status": s.get("sla_status"),
                    "sla_due_days": s.get("sla_due_days"),
                }
            )
        return {"sow_id": public_id, "status": doc.get("status"), "stages": out}

    @staticmethod
    async def approve_stage(
        public_id: str, stage_key: ApprovalStageKey, reviewer: str, comments: Optional[str], user: Dict[str, Any]
    ) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        auth = doc.get("approval_authorities") or {}
        expected = reviewer_email_for_stage(auth, stage_key)
        if not expected or _normalize_email(reviewer) != expected or _normalize_email(reviewer) != _normalize_email(
            user.get("email") or ""
        ):
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Not the designated reviewer for this stage")
        stages: List[Dict[str, Any]] = list(doc.get("approval_stages") or [])
        idx = next((i for i, s in enumerate(stages) if s["stage"] == stage_key.value), None)
        if idx is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=409, detail="Pipeline not initialized")
        if stages[idx]["status"] != ApprovalStageStatus.in_review.value:
            raise_spec(409, "Stage is not in review", "invalid_stage_state")
        now = _utcnow()
        stages[idx]["status"] = ApprovalStageStatus.approved.value
        stages[idx]["reviewer"] = reviewer
        stages[idx]["reviewed_at"] = now
        stages[idx]["comments"] = comments
        next_stage_name: Optional[str] = None
        if idx < len(stages) - 1:
            stages[idx + 1]["status"] = ApprovalStageStatus.in_review.value
            next_stage_name = stages[idx + 1]["stage"]
        col = get_manual_sows_collection()
        update: Dict[str, Any] = {"approval_stages": stages, "updated_at": now}
        if idx == len(stages) - 1:
            update["status"] = ManualSowStatus.approved.value
            update["approved_at"] = now
            update["approved_by"] = reviewer
        await col.update_one({"public_id": public_id}, {"$set": update})
        await ManualSowService._append_message(
            public_id,
            idx,
            stage_key.value,
            "stage_approved",
            user.get("full_name") or reviewer,
            "Reviewer",
            "",
            "",
            f"Stage {stage_key.value} approved",
            comments or "",
        )
        return {
            "sow_id": public_id,
            "stage": stage_key.value,
            "status": "approved",
            "reviewed_at": now.isoformat().replace("+00:00", "Z"),
            "next_stage": next_stage_name,
        }

    @staticmethod
    async def reject_stage(
        public_id: str, stage_key: ApprovalStageKey, reviewer: str, reason: str, feedback: Optional[str], user: Dict[str, Any]
    ) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        auth = doc.get("approval_authorities") or {}
        expected = reviewer_email_for_stage(auth, stage_key)
        if not expected or _normalize_email(reviewer) != expected or _normalize_email(reviewer) != _normalize_email(
            user.get("email") or ""
        ):
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Not the designated reviewer for this stage")
        stages: List[Dict[str, Any]] = list(doc.get("approval_stages") or [])
        idx = next((i for i, s in enumerate(stages) if s["stage"] == stage_key.value), None)
        if idx is None or stages[idx]["status"] != ApprovalStageStatus.in_review.value:
            raise_spec(409, "Stage not in review", "invalid_stage_state")
        now = _utcnow()
        stages[idx]["status"] = ApprovalStageStatus.rejected.value
        stages[idx]["reviewer"] = reviewer
        stages[idx]["reviewed_at"] = now
        stages[idx]["comments"] = reason
        for j, s in enumerate(stages):
            if j != idx:
                s["status"] = ApprovalStageStatus.pending.value
                s["reviewer"] = None
                s["reviewed_at"] = None
        cr_id = str(uuid.uuid4())
        col = get_manual_sows_collection()
        new_version = int(doc.get("version") or 1) + 1
        await col.update_one(
            {"public_id": public_id},
            {
                "$set": {
                    "approval_stages": stages,
                    "status": ManualSowStatus.changes_requested.value,
                    "version": new_version,
                    "updated_at": now,
                },
                "$push": {
                    "change_requests": {
                        "id": cr_id,
                        "requested_at": now,
                        "reason": reason,
                        "feedback": feedback or "",
                        "stage": stage_key.value,
                        "reviewer": reviewer,
                    }
                },
            },
        )
        return {
            "sow_id": public_id,
            "status": ManualSowStatus.changes_requested.value,
            "rejected_stage": {"stage": stage_key.value, "status": "rejected"},
            "change_request": {
                "id": cr_id,
                "requested_at": now.isoformat().replace("+00:00", "Z"),
                "reason": reason,
                "feedback": feedback or "",
            },
        }

    @staticmethod
    async def list_messages(public_id: str, stage: Optional[str], limit: int) -> Dict[str, Any]:
        col = get_manual_sow_approval_messages_collection()
        q: Dict[str, Any] = {"sow_public_id": public_id}
        if stage:
            q["stage_key"] = stage
        msgs: List[Dict[str, Any]] = []
        cur = col.find(q).sort("sent_at", -1).limit(limit)
        async for m in cur:
            msgs.append(
                {
                    "id": m["public_id"],
                    "stage_index": m["stage_index"],
                    "stage_key": m["stage_key"],
                    "type": m["type"],
                    "sender_name": m.get("sender_name"),
                    "sender_role": m.get("sender_role"),
                    "recipient_name": m.get("recipient_name"),
                    "recipient_role": m.get("recipient_role"),
                    "subject": m.get("subject"),
                    "body": m.get("body"),
                    "sent_at": m["sent_at"].isoformat().replace("+00:00", "Z"),
                    "read": m.get("read", False),
                }
            )
        msgs.reverse()
        return {"sow_id": public_id, "messages": msgs}

    @staticmethod
    async def mark_message_read(sow_public_id: str, message_id: str) -> Dict[str, Any]:
        col = get_manual_sow_approval_messages_collection()
        m = await col.find_one({"sow_public_id": sow_public_id, "public_id": message_id})
        if not m:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Message not found")
        now = _utcnow()
        await col.update_one({"_id": m["_id"]}, {"$set": {"read": True, "read_at": now}})
        return {"id": message_id, "read": True, "marked_at": now.isoformat().replace("+00:00", "Z")}

    @staticmethod
    async def list_sows(
        user_id: str,
        status: Optional[str],
        intake_mode: Optional[str],
        client: Optional[str],
        created_by: Optional[str],
        page: int,
        limit: int,
        sort: str,
        order: str,
    ) -> Dict[str, Any]:
        col = get_manual_sows_collection()
        q: Dict[str, Any] = {"deleted_at": None}
        q["created_by_user_id"] = created_by if created_by else user_id
        if status:
            q["status"] = status
        if intake_mode:
            q["intake_mode"] = intake_mode
        if client:
            q["client"] = {"$regex": client, "$options": "i"}
        sort_dir = -1 if order == "desc" else 1
        sort_field = sort if sort in ("created_at", "updated_at", "title") else "created_at"
        total = await col.count_documents(q)
        skip = (page - 1) * limit
        cursor = col.find(q).sort(sort_field, sort_dir).skip(skip).limit(limit)
        rows: List[Dict[str, Any]] = []
        async for doc in cursor:
            rows.append(
                {
                    "id": doc["public_id"],
                    "title": doc.get("title"),
                    "client": doc.get("client"),
                    "status": doc.get("status"),
                    "ai_confidence": doc.get("ai_confidence"),
                    "updated_at": doc.get("updated_at"),
                }
            )
        total_pages = (total + limit - 1) // limit if limit else 1
        return {
            "sows": rows,
            "pagination": {"page": page, "limit": limit, "total": total, "total_pages": total_pages},
        }

    @staticmethod
    async def get_full_sow(public_id: str) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        doc = dict(doc)
        doc["id"] = doc.pop("public_id")
        doc.pop("_id", None)
        return doc

    @staticmethod
    async def patch_metadata(public_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        col = get_manual_sows_collection()
        updates: Dict[str, Any] = {}
        if body.get("title") is not None:
            updates["title"] = body["title"]
        if body.get("tags") is not None:
            updates["tags"] = body["tags"]
        if body.get("stakeholders") is not None:
            updates["stakeholders"] = body["stakeholders"]
        if body.get("estimated_budget") is not None:
            updates["estimated_budget"] = body["estimated_budget"]
        updates["updated_at"] = _utcnow()
        await col.update_one({"public_id": public_id}, {"$set": updates})
        return {"id": public_id, "title": updates.get("title"), "updated_at": updates["updated_at"].isoformat().replace("+00:00", "Z")}

    @staticmethod
    async def soft_delete(public_id: str) -> None:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        st = doc.get("status")
        if st not in (ManualSowStatus.draft.value, ManualSowStatus.parsing.value, ManualSowStatus.review.value):
            raise_spec(409, "SOW cannot be deleted in current status", "invalid_status")
        col = get_manual_sows_collection()
        await col.update_one(
            {"public_id": public_id},
            {"$set": {"status": ManualSowStatus.archived.value, "deleted_at": _utcnow(), "updated_at": _utcnow()}},
        )

    @staticmethod
    async def sections_list(public_id: str) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        gen = (doc.get("generated") or {}).get("content") or {}
        secs = gen.get("sections") or []
        out = []
        for i, s in enumerate(secs):
            out.append(
                {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{public_id}-sec-{i}")),
                    "title": s.get("title"),
                    "content": s.get("content"),
                    "ai_suggestion": "",
                    "confidence": s.get("confidence"),
                    "order": i + 1,
                }
            )
        return {"sow_id": public_id, "sections": out}

    @staticmethod
    async def clauses_list(public_id: str, clause_type: Optional[str], is_prohibited: Optional[bool]) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        stored = doc.get("parsed_clauses") or []
        if not stored:
            secs = ((doc.get("generated") or {}).get("content") or {}).get("sections") or []
            for s in secs:
                stored.append(
                    {
                        "id": str(uuid.uuid4()),
                        "text": (s.get("content") or "")[:500],
                        "type": "acceptance_criteria",
                        "section_ref": s.get("title"),
                        "confidence": s.get("confidence", 80),
                        "is_prohibited": False,
                    }
                )
        out = []
        for c in stored:
            if clause_type and c.get("type") != clause_type:
                continue
            if is_prohibited is not None and bool(c.get("is_prohibited")) != is_prohibited:
                continue
            out.append(c)
        return {"sow_id": public_id, "clauses": out}

    @staticmethod
    async def hallucination_layers(public_id: str) -> Dict[str, Any]:
        doc = await ManualSowService.get_sow_doc(public_id)
        if not doc:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="SOW not found")
        gen = doc.get("generated") or {}
        layers = []
        for L in gen.get("hallucination_layers_raw") or []:
            layers.append(
                {
                    "layer": L["layer_id"],
                    "name": L["name"],
                    "status": map_layer_status(L.get("status", "grey")),
                    "details": L.get("detail", ""),
                }
            )
        return {"sow_id": public_id, "layers": layers}

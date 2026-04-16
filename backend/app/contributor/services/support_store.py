"""In-memory support hub (FAQs, tickets, grievances, safety). Replace with DB in production."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.contributor.schemas.support import (
    FAQItem,
    GrievanceCategory,
    GrievanceDetail,
    GrievanceListItem,
    SafetyCategory,
    TicketCategory,
    TicketDetail,
    TicketListItem,
    TicketMessage,
    TicketPriority,
    TicketStatus,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SupportStore:
    def __init__(self) -> None:
        self._faqs: list[dict[str, Any]] = []
        self._tickets: dict[str, dict[str, Any]] = {}
        self._grievances: dict[str, dict[str, Any]] = {}
        self._safety: list[dict[str, Any]] = []
        self._seeded = False

    def ensure_demo_seed(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        t0 = _now()
        self._faqs = [
            {
                "id": "faq_001",
                "category": "account",
                "question": "How do I update payout preferences?",
                "answer": "Go to Settings → Payout preferences or use GET/PUT /api/contributor/payout-preferences.",
            },
            {
                "id": "faq_002",
                "category": "technical",
                "question": "Why is my task upload failing?",
                "answer": "Check file size limits and allowed MIME types in the workroom upload endpoint.",
            },
            {
                "id": "faq_003",
                "category": "payment",
                "question": "When will eligible earnings move to paid?",
                "answer": "After KYC verification and the next payout batch; see earnings detail for expected dates.",
            },
            {
                "id": "faq_004",
                "category": "task_question",
                "question": "Can I request a deadline extension?",
                "answer": "Yes — use POST /api/contributor/tasks/{task_id}/request-extension with reason and new date.",
            },
            {
                "id": "faq_005",
                "category": "safety",
                "question": "How do I report a safety concern?",
                "answer": "Use POST /api/contributor/support/safety-reports with category and description.",
            },
        ]
        self._tickets["tkt_demo_001"] = {
            "id": "tkt_demo_001",
            "subject": "Cannot access workroom for tsk_002",
            "category": TicketCategory.technical,
            "priority": TicketPriority.high,
            "status": TicketStatus.in_progress,
            "description": "Spinner never finishes loading the workroom tab.",
            "attachment_ids": ["att_1"],
            "related_task_id": "tsk_002",
            "related_project_id": "prj_002",
            "created_at": t0,
            "updated_at": t0,
            "messages": [
                {
                    "id": "msg_t_1",
                    "author": "contributor",
                    "message": "Started yesterday after deploy.",
                    "attachment_ids": [],
                    "created_at": t0,
                },
                {
                    "id": "msg_t_2",
                    "author": "support",
                    "message": "Thanks — please try a hard refresh; we cleared a stale CDN cache.",
                    "attachment_ids": [],
                    "created_at": t0,
                },
            ],
        }
        self._tickets["tkt_demo_002"] = {
            "id": "tkt_demo_002",
            "subject": "Question on payment hold",
            "category": TicketCategory.payment,
            "priority": TicketPriority.medium,
            "status": TicketStatus.waiting_on_user,
            "description": "Earning ern_004 shows on_hold — what document is needed?",
            "attachment_ids": [],
            "related_task_id": "tsk_005",
            "related_project_id": None,
            "created_at": t0,
            "updated_at": t0,
            "messages": [],
        }
        self._grievances["grv_demo_001"] = {
            "id": "grv_demo_001",
            "category": GrievanceCategory.review_dispute,
            "subject": "Disagree with review score on batch 12",
            "description": "Rubric says coverage was complete; reviewer marked partial.",
            "related_reference": "sub_demo_submitted",
            "anonymous": False,
            "attachment_ids": [],
            "status": "under_review",
            "created_at": t0,
            "updated_at": t0,
        }
        self._safety.append(
            {
                "id": "sfty_demo_001",
                "category": SafetyCategory.inappropriate,
                "description": "Seeded safety report for API testing (not a real incident).",
                "related_reference": "thr_demo_1",
                "attachment_ids": [],
                "status": "received",
                "created_at": t0,
            }
        )
        self._inject_e2e_support_rows(t0)

    def _inject_e2e_support_rows(self, t0: datetime) -> None:
        """Extra tickets / grievances / FAQs for filter and lifecycle E2E tests."""
        if "tkt_e2e_open" in self._tickets:
            return
        self._tickets["tkt_e2e_open"] = {
            "id": "tkt_e2e_open",
            "subject": "Login loop on mobile web",
            "category": TicketCategory.account,
            "priority": TicketPriority.low,
            "status": TicketStatus.open,
            "description": "After SSO, page redirects back to login.",
            "attachment_ids": [],
            "related_task_id": None,
            "related_project_id": None,
            "created_at": t0,
            "updated_at": t0,
            "messages": [],
        }
        self._tickets["tkt_e2e_resolved"] = {
            "id": "tkt_e2e_resolved",
            "subject": "Invoice PDF typo",
            "category": TicketCategory.payment,
            "priority": TicketPriority.low,
            "status": TicketStatus.resolved,
            "description": "Spelling on line 2 of payout receipt.",
            "attachment_ids": [],
            "related_task_id": None,
            "related_project_id": None,
            "created_at": t0,
            "updated_at": t0,
            "messages": [
                {
                    "id": "msg_res_1",
                    "author": "support",
                    "message": "Fixed in next deploy.",
                    "attachment_ids": [],
                    "created_at": t0,
                },
            ],
        }
        self._tickets["tkt_e2e_closed"] = {
            "id": "tkt_e2e_closed",
            "subject": "Timezone display wrong",
            "category": TicketCategory.technical,
            "priority": TicketPriority.medium,
            "status": TicketStatus.closed,
            "description": "Settings showed UTC only.",
            "attachment_ids": [],
            "related_task_id": "tsk_002",
            "related_project_id": "prj_002",
            "created_at": t0,
            "updated_at": t0,
            "messages": [],
        }
        self._grievances["grv_e2e_anon"] = {
            "id": "grv_e2e_anon",
            "category": GrievanceCategory.other,
            "subject": "Team matching concern",
            "description": "Details omitted for anonymity in list views.",
            "related_reference": None,
            "anonymous": True,
            "attachment_ids": [],
            "status": "submitted",
            "created_at": t0,
            "updated_at": t0,
        }
        self._faqs.extend(
            [
                {
                    "id": "faq_e2e_01",
                    "category": "safety",
                    "question": "What counts as harassment in task comments?",
                    "answer": "See the safety reporting API and community guidelines; use POST /api/contributor/support/safety-reports for incidents.",
                },
                {
                    "id": "faq_e2e_02",
                    "category": "account",
                    "question": "How do I enable two-factor authentication?",
                    "answer": "Settings → security: POST /settings/security/2fa/setup then verify with your authenticator app.",
                },
            ]
        )
        self._safety.append(
            {
                "id": "sfty_e2e_002",
                "category": SafetyCategory.fraud,
                "description": "E2E placeholder — suspicious payout request (demo only).",
                "related_reference": "ern_001",
                "attachment_ids": ["att_sfty_1"],
                "status": "received",
                "created_at": t0,
            }
        )

    def list_faqs(self, category: str | None, q: str | None) -> tuple[list[FAQItem], int]:
        self.ensure_demo_seed()
        items = list(self._faqs)
        if category and category.strip():
            c = category.strip().lower()
            items = [x for x in items if x["category"].lower() == c]
        if q and q.strip():
            needle = q.strip().lower()
            items = [
                x
                for x in items
                if needle in x["question"].lower() or needle in x["answer"].lower()
            ]
        out = [FAQItem(**x) for x in items]
        return out, len(out)

    def list_tickets(
        self,
        *,
        status: TicketStatus | None,
        priority: TicketPriority | None,
        category: TicketCategory | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TicketListItem], int]:
        self.ensure_demo_seed()
        rows = list(self._tickets.values())
        if status is not None:
            rows = [r for r in rows if r["status"] == status]
        if priority is not None:
            rows = [r for r in rows if r["priority"] == priority]
        if category is not None:
            rows = [r for r in rows if r["category"] == category]
        rows.sort(key=lambda r: r["updated_at"], reverse=True)
        total = len(rows)
        start = (page - 1) * page_size
        slice_ = rows[start : start + page_size]
        items = [
            TicketListItem(
                id=r["id"],
                subject=r["subject"],
                category=r["category"],
                priority=r["priority"],
                status=r["status"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in slice_
        ]
        return items, total

    def get_ticket(self, ticket_id: str) -> TicketDetail | None:
        self.ensure_demo_seed()
        r = self._tickets.get(ticket_id)
        if not r:
            return None
        msgs = [
            TicketMessage(
                id=m["id"],
                author=m["author"],
                message=m["message"],
                attachment_ids=list(m.get("attachment_ids", [])),
                created_at=m["created_at"],
            )
            for m in r["messages"]
        ]
        return TicketDetail(
            id=r["id"],
            subject=r["subject"],
            category=r["category"],
            priority=r["priority"],
            status=r["status"],
            description=r["description"],
            attachment_ids=list(r.get("attachment_ids", [])),
            related_task_id=r.get("related_task_id"),
            related_project_id=r.get("related_project_id"),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            messages=msgs,
        )

    def create_ticket(self, data: dict[str, Any]) -> TicketDetail:
        self.ensure_demo_seed()
        tid = f"tkt_{uuid.uuid4().hex[:12]}"
        now = _now()
        row = {
            "id": tid,
            "subject": data["subject"],
            "category": data["category"],
            "priority": data["priority"],
            "status": TicketStatus.open,
            "description": data["description"],
            "attachment_ids": list(data.get("attachment_ids", [])),
            "related_task_id": data.get("related_task_id"),
            "related_project_id": data.get("related_project_id"),
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        self._tickets[tid] = row
        d = self.get_ticket(tid)
        assert d is not None
        return d

    def add_ticket_message(self, ticket_id: str, message: str, attachment_ids: list[str]) -> TicketMessage | None:
        self.ensure_demo_seed()
        r = self._tickets.get(ticket_id)
        if not r:
            return None
        now = _now()
        m = {
            "id": f"msg_{uuid.uuid4().hex[:10]}",
            "author": "contributor",
            "message": message,
            "attachment_ids": list(attachment_ids),
            "created_at": now,
        }
        r["messages"].append(m)
        r["updated_at"] = now
        if r["status"] == TicketStatus.waiting_on_user:
            r["status"] = TicketStatus.in_progress
        return TicketMessage(**m)

    def create_grievance(self, data: dict[str, Any]) -> GrievanceDetail:
        self.ensure_demo_seed()
        gid = f"grv_{uuid.uuid4().hex[:12]}"
        now = _now()
        row = {
            "id": gid,
            "category": data["category"],
            "subject": data["subject"],
            "description": data["description"],
            "related_reference": data.get("related_reference"),
            "anonymous": bool(data.get("anonymous", False)),
            "attachment_ids": list(data.get("attachment_ids", [])),
            "status": "submitted",
            "created_at": now,
            "updated_at": now,
        }
        self._grievances[gid] = row
        return self._grievance_to_detail(row)

    def list_grievances(self) -> tuple[list[GrievanceListItem], int]:
        self.ensure_demo_seed()
        rows = sorted(self._grievances.values(), key=lambda x: x["created_at"], reverse=True)
        items = [
            GrievanceListItem(
                id=r["id"],
                category=r["category"],
                subject=r["subject"] if not r["anonymous"] else "[Anonymous]",
                status=r["status"],
                created_at=r["created_at"],
                anonymous=r["anonymous"],
            )
            for r in rows
        ]
        return items, len(items)

    def get_grievance(self, grievance_id: str) -> GrievanceDetail | None:
        self.ensure_demo_seed()
        r = self._grievances.get(grievance_id)
        if not r:
            return None
        return self._grievance_to_detail(r)

    def _grievance_to_detail(self, r: dict[str, Any]) -> GrievanceDetail:
        return GrievanceDetail(
            id=r["id"],
            category=r["category"],
            subject=r["subject"],
            description=r["description"],
            related_reference=r.get("related_reference"),
            anonymous=r["anonymous"],
            attachment_ids=list(r.get("attachment_ids", [])),
            status=r["status"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def create_safety_report(self, data: dict[str, Any]) -> dict[str, Any]:
        self.ensure_demo_seed()
        sid = f"sfty_{uuid.uuid4().hex[:12]}"
        now = _now()
        row = {
            "id": sid,
            "category": data["category"],
            "description": data["description"],
            "related_reference": data.get("related_reference"),
            "attachment_ids": list(data.get("attachment_ids", [])),
            "status": "received",
            "created_at": now,
        }
        self._safety.append(row)
        return row


store = SupportStore()


def apply_temp_demo_seed() -> None:
    """Idempotent; ensures demo FAQs/tickets/grievances exist."""
    store.ensure_demo_seed()

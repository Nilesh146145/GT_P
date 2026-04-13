"""In-memory message store. Replace with database persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from app.contributor.schemas.messages import (
    MessageInThread,
    Participant,
    SenderRole,
    ThreadDetail,
    ThreadListItem,
)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class StoredMessage:
    id: str
    thread_id: str
    sender_id: str
    sender_name: str
    sender_role: SenderRole
    content: str
    timestamp: datetime
    attachment_ids: list[str]
    rating: Literal["up", "down"] | None = None


@dataclass
class StoredThread:
    id: str
    project_name: str
    task_id: str | None
    task_title: str | None
    participants: list[Participant]
    messages: list[StoredMessage] = field(default_factory=list)
    unread_count: int = 0


class MessagesStore:
    def __init__(self) -> None:
        self._threads: dict[str, StoredThread] = {}
        self._seed()

    def _seed(self) -> None:
        t1 = "thr_demo_1"
        t2 = "thr_demo_2"
        self._threads[t1] = StoredThread(
            id=t1,
            project_name="Glimmora Web",
            task_id="tsk_002",
            task_title="Build funnel chart",
            participants=[
                Participant(
                    id="u_mentor_1",
                    name="Alex Kim",
                    role=SenderRole.mentor,
                    avatar="https://example.com/a.png",
                ),
                Participant(
                    id="u_me",
                    name="You",
                    role=SenderRole.project_team,
                ),
            ],
            messages=[
                StoredMessage(
                    id="msg_1",
                    thread_id=t1,
                    sender_id="u_mentor_1",
                    sender_name="Alex Kim",
                    sender_role=SenderRole.mentor,
                    content="Great progress on the funnel chart — wire up the D3 transitions next.",
                    timestamp=_now(),
                    attachment_ids=[],
                    rating=None,
                ),
            ],
            unread_count=1,
        )
        self._threads[t2] = StoredThread(
            id=t2,
            project_name="Glimmora Web",
            task_id=None,
            task_title=None,
            participants=[
                Participant(
                    id="ai_1",
                    name="Assistant",
                    role=SenderRole.ai_assistant,
                ),
            ],
            messages=[
                StoredMessage(
                    id="msg_ai_1",
                    thread_id=t2,
                    sender_id="ai_1",
                    sender_name="Assistant",
                    sender_role=SenderRole.ai_assistant,
                    content="How can I help with your task today?",
                    timestamp=_now(),
                    attachment_ids=[],
                    rating=None,
                ),
            ],
            unread_count=0,
        )

    def list_threads(
        self,
        role_filter: str,
        q: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ThreadListItem], int]:
        items: list[ThreadListItem] = []
        for th in self._threads.values():
            last = th.messages[-1] if th.messages else None
            if not last:
                continue
            if role_filter != "all" and last.sender_role.value != role_filter:
                continue
            if q:
                needle = q.lower()
                if needle not in last.content.lower() and needle not in th.project_name.lower():
                    continue
            peer = th.participants[0] if th.participants else None
            sender_name = peer.name if peer else "Unknown"
            sender_role = peer.role if peer else SenderRole.project_team
            items.append(
                ThreadListItem(
                    id=th.id,
                    sender_name=sender_name,
                    sender_role=sender_role,
                    project_name=th.project_name,
                    task_id=th.task_id,
                    task_title=th.task_title,
                    last_message=last.content,
                    timestamp=last.timestamp,
                    unread=th.unread_count > 0,
                    unread_count=th.unread_count,
                    avatar=peer.avatar if peer else None,
                )
            )
        items.sort(key=lambda x: x.timestamp, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def get_thread(self, thread_id: str) -> StoredThread | None:
        return self._threads.get(thread_id)

    def thread_to_detail(self, th: StoredThread) -> ThreadDetail:
        return ThreadDetail(
            id=th.id,
            participants=list(th.participants),
            task_id=th.task_id,
            project_name=th.project_name,
            messages=[
                MessageInThread(
                    id=m.id,
                    sender_id=m.sender_id,
                    sender_name=m.sender_name,
                    sender_role=m.sender_role,
                    content=m.content,
                    timestamp=m.timestamp,
                    attachment_ids=list(m.attachment_ids),
                    rating=m.rating,
                )
                for m in sorted(th.messages, key=lambda x: x.timestamp)
            ],
        )

    def add_message(
        self,
        thread_id: str,
        content: str,
        attachment_ids: list[str],
    ) -> StoredMessage | None:
        th = self._threads.get(thread_id)
        if not th:
            return None
        msg = StoredMessage(
            id=f"msg_{uuid4().hex[:12]}",
            thread_id=thread_id,
            sender_id="u_me",
            sender_name="You",
            sender_role=SenderRole.project_team,
            content=content,
            timestamp=_now(),
            attachment_ids=list(attachment_ids),
            rating=None,
        )
        th.messages.append(msg)
        return msg

    def mark_read(self, thread_id: str) -> bool:
        th = self._threads.get(thread_id)
        if not th:
            return False
        th.unread_count = 0
        return True

    def set_message_rating(
        self,
        message_id: str,
        rating: Literal["up", "down"],
    ) -> bool:
        for th in self._threads.values():
            for m in th.messages:
                if m.id == message_id:
                    m.rating = rating
                    return True
        return False

    def apply_temp_demo_seed(self) -> None:
        if "thr_demo_etl" not in self._threads:
            te = "thr_demo_etl"
            self._threads[te] = StoredThread(
                id=te,
                project_name="Finance Data",
                task_id="tsk_005",
                task_title="ETL pipeline hardening",
                participants=[
                    Participant(
                        id="u_reviewer_1",
                        name="Sam Patel",
                        role=SenderRole.mentor,
                        avatar=None,
                    ),
                    Participant(
                        id="u_me",
                        name="You",
                        role=SenderRole.project_team,
                    ),
                ],
                messages=[
                    StoredMessage(
                        id="msg_etl_rework",
                        thread_id=te,
                        sender_id="u_reviewer_1",
                        sender_name="Sam Patel",
                        sender_role=SenderRole.mentor,
                        content="Please add null handling for empty partitions per the rubric feedback.",
                        timestamp=_now(),
                        attachment_ids=[],
                        rating=None,
                    ),
                ],
                unread_count=1,
            )
        if "thr_demo_support" in self._threads:
            return
        tid = "thr_demo_support"
        self._threads[tid] = StoredThread(
            id=tid,
            project_name="Glimmora Support",
            task_id=None,
            task_title=None,
            participants=[
                Participant(
                    id="u_support_1",
                    name="Support Bot",
                    role=SenderRole.project_team,
                    avatar=None,
                ),
            ],
            messages=[
                StoredMessage(
                    id="msg_support_welcome",
                    thread_id=tid,
                    sender_id="u_support_1",
                    sender_name="Support Bot",
                    sender_role=SenderRole.project_team,
                    content="Hi! This thread is seeded for temp_api_db message API checks.",
                    timestamp=_now(),
                    attachment_ids=[],
                    rating=None,
                ),
            ],
            unread_count=1,
        )


store = MessagesStore()

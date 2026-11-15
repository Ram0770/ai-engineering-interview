"""Asynchronous notification queue and pull inbox store."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("agent_network.queue")


@dataclass
class NotificationJob:
    """Queued delivery task representing an approved routing event."""

    post_id: str
    target_agent_id: str
    target_company: str
    webhook_url: str
    signing_secret: str
    payload: dict[str, Any]
    attempts: int = 0
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationQueue:
    """In-process asynchronous job queue with inbox polling fallback."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[NotificationJob] = asyncio.Queue()
        # In-memory inbox for pull delivery: agent_id -> list of notifications
        self._inbox_store: dict[str, list[dict[str, Any]]] = {}
        # Dead-Letter Queue for permanently failed deliveries
        self._dead_letter_queue: list[NotificationJob] = []
        self._worker_task: asyncio.Task[None] | None = None
        self._running: bool = False

    async def enqueue(self, job: NotificationJob) -> None:
        """Pushes a notification job to the dispatch queue and stores a copy in the pull inbox."""
        await self._queue.put(job)

        # Store in pull inbox so agents behind NAT can poll immediately
        agent_id = job.target_agent_id
        if agent_id not in self._inbox_store:
            self._inbox_store[agent_id] = []

        inbox_entry = {
            "post_id": job.post_id,
            "target_agent_id": job.target_agent_id,
            "payload": job.payload,
            "timestamp": job.enqueued_at.isoformat(),
            "read": False,
        }
        self._inbox_store[agent_id].append(inbox_entry)

    def get_inbox_messages(self, agent_id: str, mark_as_read: bool = True) -> list[dict[str, Any]]:
        """Retrieves and optionally marks as read queued inbox notifications for an agent."""
        messages = self._inbox_store.get(agent_id, [])
        if mark_as_read:
            for m in messages:
                m["read"] = True
        return list(messages)

    def enqueue_dead_letter(self, job: NotificationJob) -> None:
        """Stores a permanently failed job in the Dead-Letter Queue."""
        self._dead_letter_queue.append(job)
        logger.warning(
            f"Job permanently moved to DLQ: target={job.target_company} (agent_id={job.target_agent_id}) "
            f"post_id={job.post_id} after {job.attempts} attempts."
        )

    @property
    def dlq_jobs(self) -> list[NotificationJob]:
        return list(self._dead_letter_queue)


# Singleton queue instance
notification_queue = NotificationQueue()

"""Pull inbox API for polling notifications."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.deps import get_current_agent
from src.db.models import Agent
from src.notifications.queue import notification_queue

router = APIRouter(tags=["Inbox"])


class InboxNotification(BaseModel):
    post_id: str
    target_agent_id: str
    payload: dict[str, Any]
    timestamp: str
    read: bool


@router.get("/agents/me/inbox", response_model=list[InboxNotification])
@router.get("/inbox", response_model=list[InboxNotification])
async def poll_inbox(
    mark_as_read: bool = True,
    current_agent: Agent = Depends(get_current_agent),
) -> list[InboxNotification]:
    """Polls queued notifications for agents behind NAT or firewalls without public webhooks."""
    messages = notification_queue.get_inbox_messages(current_agent.id, mark_as_read=mark_as_read)
    return [
        InboxNotification(
            post_id=m["post_id"],
            target_agent_id=m["target_agent_id"],
            payload=m["payload"],
            timestamp=m["timestamp"],
            read=m["read"],
        )
        for m in messages
    ]

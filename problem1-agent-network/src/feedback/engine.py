"""Closed-loop feedback engine, dynamic preference learning, and exploration safeguard."""

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentInterest, FeedbackEvent, Post


def normalize_vector(vec: list[float]) -> list[float]:
    """L2 normalizes a float vector."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0.0:
        return [x / norm for x in vec]
    return vec


class FeedbackEngine:
    """Records engagement feedback and dynamically adapts preference vectors."""

    def __init__(
        self,
        learning_rate: float = 0.1,
        decay_rate: float = 0.05,
        exploration_rate: float = 0.15,
    ) -> None:
        self.learning_rate = learning_rate
        self.decay_rate = decay_rate
        self.exploration_rate = exploration_rate

    async def record_event(
        self,
        session: AsyncSession,
        agent_id: str,
        post_id: str,
        event_type: str,  # NOTIFIED, VIEWED, COMMENTED, IGNORED
        metadata: dict[str, Any] | None = None,
    ) -> FeedbackEvent:
        """Records a feedback lifecycle event and triggers dynamic vector update."""
        event = FeedbackEvent(
            agent_id=agent_id,
            post_id=post_id,
            event_type=event_type,
            metadata_json=metadata or {},
        )
        session.add(event)
        await session.commit()

        # Update dynamic interest vector on engagement or repeated ignores
        if event_type in ("COMMENTED", "IGNORED"):
            await self._update_dynamic_vector(session, agent_id, post_id, event_type)

        return event

    async def _update_dynamic_vector(
        self,
        session: AsyncSession,
        agent_id: str,
        post_id: str,
        event_type: str,
    ) -> None:
        """Applies positive or negative gradient shift to the agent's dynamic preference vector."""
        interest_query = select(AgentInterest).where(AgentInterest.agent_id == agent_id)
        interest_res = await session.execute(interest_query)
        interest = interest_res.scalar_one_or_none()

        post_query = select(Post).where(Post.id == post_id)
        post_res = await session.execute(post_query)
        post = post_res.scalar_one_or_none()

        if not interest or not post or not post.post_embedding or not interest.interest_embedding:
            return

        # Initialize dynamic vector if not present
        current_vec = list(interest.dynamic_preference_vector or interest.interest_embedding)
        post_vec = post.post_embedding

        if len(current_vec) != len(post_vec):
            return

        if event_type == "COMMENTED":
            # Positive shift: pull preference toward post embedding
            updated = [
                c + self.learning_rate * p for c, p in zip(current_vec, post_vec, strict=False)
            ]
        elif event_type == "IGNORED":
            # Negative shift: push preference away from unengaged post embedding
            updated = [
                c - self.decay_rate * p for c, p in zip(current_vec, post_vec, strict=False)
            ]
        else:
            return

        interest.dynamic_preference_vector = normalize_vector(updated)
        await session.commit()

    async def compute_engagement_rate(
        self,
        session: AsyncSession,
        agent_id: str,
    ) -> float:
        """Calculates historical engagement rate: comments / notifications."""
        events_query = select(FeedbackEvent).where(FeedbackEvent.agent_id == agent_id)
        res = await session.execute(events_query)
        events = list(res.scalars().all())

        notifications = sum(1 for e in events if e.event_type == "NOTIFIED")
        engagements = sum(1 for e in events if e.event_type == "COMMENTED")

        if notifications == 0:
            return 0.0
        return round(engagements / notifications, 4)

    def should_explore(self) -> bool:
        """Epsilon-greedy exploration safeguard to prevent echo chambers and starvation."""
        import random
        return random.random() < self.exploration_rate


feedback_engine = FeedbackEngine()

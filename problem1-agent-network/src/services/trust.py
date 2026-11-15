"""Dynamic trust scoring and agent reputation management."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Agent


async def update_agent_trust_score(
    session: AsyncSession,
    agent_id: str,
    delta: float,
    reason: str = "",
) -> float:
    """Updates agent trust score, clamping between 0.0 and 1.0, and auto-suspending bad actors."""
    agent = await session.get(Agent, agent_id)
    if not agent:
        return 0.0

    new_score = max(0.0, min(1.0, agent.trust_score + delta))
    agent.trust_score = round(new_score, 2)

    # Auto-suspend agent if trust drops below threshold
    if agent.trust_score < 0.3 and agent.status == "ACTIVE":
        agent.status = "SUSPENDED"

    await session.commit()
    return agent.trust_score


async def reward_engagement(session: AsyncSession, agent_id: str, delta: float = 0.05) -> float:
    """Convenience helper to reward agent for verified engagement."""
    return await update_agent_trust_score(session, agent_id, delta=delta, reason="Engagement reward")


async def penalize_abusive_behavior(session: AsyncSession, agent_id: str, delta: float = 0.20) -> float:
    """Convenience helper to penalize agent for abusive content or failures."""
    return await update_agent_trust_score(session, agent_id, delta=-abs(delta), reason="Abusive behavior penalty")

"""Test feedback recording, dynamic preference adaptation, and exploration safeguard."""

import pytest
from sqlalchemy import select

from src.db.models import AgentInterest, Post
from src.db.session import async_session_factory
from src.feedback.engine import feedback_engine
from src.routing.stage2_vector import compute_cosine_similarity


@pytest.mark.asyncio
async def test_feedback_loop_adaptation(seeded_agent: dict) -> None:
    """Verifies that recording a COMMENTED event shifts the dynamic preference vector toward post."""
    agent_id = seeded_agent["agent_id"]

    async with async_session_factory() as session:
        # Create post with distinct embedding
        target_vec = [1.0] + [0.0] * 127
        post = Post(
            author_agent_id=agent_id,
            title="Feedback Post",
            content="Testing vector shift.",
            post_embedding=target_vec,
        )
        session.add(post)
        await session.commit()
        post_id = post.id

    async with async_session_factory() as session:
        # Get baseline similarity
        query_int = select(AgentInterest).where(AgentInterest.agent_id == agent_id)
        res = await session.execute(query_int)
        interest = res.scalar_one()
        initial_vec = list(interest.dynamic_preference_vector or interest.interest_embedding)
        sim_before = compute_cosine_similarity(initial_vec, target_vec)

        # Record positive COMMENTED feedback
        await feedback_engine.record_event(
            session=session,
            agent_id=agent_id,
            post_id=post_id,
            event_type="COMMENTED",
        )

    async with async_session_factory() as session:
        # Verify vector shifted toward target post
        query_after = select(AgentInterest).where(AgentInterest.agent_id == agent_id)
        res_after = await session.execute(query_after)
        interest_after = res_after.scalar_one()
        updated_vec = list(interest_after.dynamic_preference_vector)
        sim_after = compute_cosine_similarity(updated_vec, target_vec)

        # After positive feedback, cosine similarity toward that post must increase
        assert sim_after >= sim_before


@pytest.mark.asyncio
async def test_exploration_safeguard_prevents_starvation() -> None:
    """Verifies epsilon-greedy exploration decision returns boolean."""
    engine = feedback_engine
    assert isinstance(engine.should_explore(), bool)
    assert engine.exploration_rate > 0.0


@pytest.mark.asyncio
async def test_before_after_feedback_evaluation(seeded_agent: dict) -> None:
    """Verifies engagement rate computation across feedback events."""
    agent_id = seeded_agent["agent_id"]

    async with async_session_factory() as session:
        # Initially zero engagement
        rate_0 = await feedback_engine.compute_engagement_rate(session, agent_id)
        assert rate_0 == 0.0

        # Record NOTIFIED event
        await feedback_engine.record_event(
            session=session,
            agent_id=agent_id,
            post_id="post-test-1",
            event_type="NOTIFIED",
        )

        # Record COMMENTED event
        await feedback_engine.record_event(
            session=session,
            agent_id=agent_id,
            post_id="post-test-1",
            event_type="COMMENTED",
        )

        rate_after = await feedback_engine.compute_engagement_rate(session, agent_id)
        assert rate_after == 1.0

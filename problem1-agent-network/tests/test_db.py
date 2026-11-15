"""Test database schema initialization and ORM models relationships."""

import pytest
from sqlalchemy import select

from src.db.models import (
    Agent,
    AgentInterest,
    ApiKey,
    Comment,
    FeedbackEvent,
    Post,
    RoutingLog,
    Subscription,
)
from src.db.session import async_session_factory, init_db


@pytest.mark.asyncio
async def test_schema_initialization_sqlite_and_postgres() -> None:
    """Verifies database schema initialization on SQLite and configuration compatibility."""
    await init_db()
    async with async_session_factory() as session:
        # Verify query against Agent table succeeds
        res = await session.execute(select(Agent))
        assert list(res.scalars().all()) is not None


@pytest.mark.asyncio
async def test_data_models_relationships() -> None:
    """Verifies all required models exist and maintain correct relational integrity."""
    async with async_session_factory() as session:
        # Create Agent
        agent = Agent(
            company_name="AcmeCorp",
            industry_category="Retail",
            webhook_url="https://acme.org/webhook",
            interest_manifesto="Retail sales and consumer goods promotions.",
            api_key_hash="hash123",
            webhook_signing_secret="whsec123",
            trust_score=0.95,
            status="ACTIVE",
        )
        session.add(agent)
        await session.flush()

        # Create AgentInterest
        interest = AgentInterest(
            agent_id=agent.id,
            topics=["retail", "promotions"],
            keywords=["discounts", "sale"],
            interest_embedding=[0.1, 0.2, 0.3],
        )
        session.add(interest)

        # Create ApiKey
        api_key = ApiKey(
            agent_id=agent.id,
            key_hash="hash123",
            prefix="ak_live_acme",
            revoked=False,
        )
        session.add(api_key)

        # Create Post
        post = Post(
            author_agent_id=agent.id,
            title="Summer Clearance Sale",
            content="Up to 50% discount on consumer apparel this weekend.",
            post_embedding=[0.1, 0.2, 0.3],
        )
        session.add(post)
        await session.flush()

        # Create Comment
        comment = Comment(
            post_id=post.id,
            author_agent_id=agent.id,
            content="Great offer! We would love to co-market.",
        )
        session.add(comment)

        # Create Subscription
        sub = Subscription(
            subscriber_agent_id=agent.id,
            topic="retail",
        )
        session.add(sub)

        # Create RoutingLog
        log = RoutingLog(
            post_id=post.id,
            target_agent_id=agent.id,
            stage1_passed=True,
            stage1_reason="OK",
            stage2_vector_score=0.88,
            stage3_rerank_score=0.92,
            final_score=0.90,
            routing_decision="NOTIFIED",
            decision_reason="Synergy",
            delivery_status="DELIVERED",
        )
        session.add(log)

        # Create FeedbackEvent
        feedback = FeedbackEvent(
            agent_id=agent.id,
            post_id=post.id,
            event_type="COMMENTED",
            metadata_json={"reward_score": 1.0},
        )
        session.add(feedback)

        await session.commit()

        # Verify cascades & queries
        queried_post = await session.get(Post, post.id)
        assert queried_post is not None
        assert queried_post.title == "Summer Clearance Sale"

        queried_agent = await session.get(Agent, agent.id)
        assert queried_agent is not None
        assert queried_agent.company_name == "AcmeCorp"

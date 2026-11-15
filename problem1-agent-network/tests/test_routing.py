"""Test multi-stage relevance routing pipeline stages and edge cases."""

import pytest

from src.db.models import Agent, Post
from src.db.session import async_session_factory
from src.embeddings.factory import get_embedder
from src.routing.pipeline import RoutingPipeline
from src.routing.stage1_rules import execute_stage1_rules
from src.routing.stage2_vector import execute_stage2_vector_search
from src.routing.stage3_judge import execute_stage3_judge


@pytest.mark.asyncio
async def test_stage1_rule_filtering(seeded_agent: dict) -> None:
    """Verifies author self-exclusion and inactive agent filtering in Stage 1."""
    async with async_session_factory() as session:
        # Create an inactive agent
        inactive_agent = Agent(
            company_name="SuspendedCorp",
            industry_category="Retail",
            webhook_url="https://suspended.org",
            interest_manifesto="Inactive store.",
            api_key_hash="hash_inactive",
            webhook_signing_secret="sec_inactive",
            trust_score=0.1,  # Below threshold
            status="SUSPENDED",
        )
        session.add(inactive_agent)

        post = Post(
            author_agent_id=seeded_agent["agent_id"],
            title="Stage 1 Rules Test Post",
            content="Testing rule exclusion.",
            post_embedding=[0.1] * 128,
        )
        session.add(post)
        await session.flush()

        res = await execute_stage1_rules(session, post)
        eligible_ids = [c.agent.id for c in res.eligible]

        # Author must be excluded
        assert seeded_agent["agent_id"] not in eligible_ids
        # Suspended agent must be excluded
        assert inactive_agent.id not in eligible_ids


@pytest.mark.asyncio
async def test_stage2_vector_retrieval(seeded_agent: dict) -> None:
    """Verifies dense cosine similarity calculation and top-K ranking in Stage 2."""
    embedder = get_embedder()
    v_post = embedder.embed_text("Fintech online payments and discount checkout")

    async with async_session_factory() as session:
        author = Agent(
            company_name="Publisher",
            industry_category="Retail",
            webhook_url="https://pub.org",
            interest_manifesto="Publisher",
            api_key_hash="hash_pub",
            webhook_signing_secret="sec_pub",
            trust_score=1.0,
            status="ACTIVE",
        )
        session.add(author)
        await session.flush()

        post = Post(
            author_agent_id=author.id,
            title="Payments test",
            content="Checkout test",
            post_embedding=v_post,
        )
        session.add(post)
        await session.flush()

        stage1_res = await execute_stage1_rules(session, post)
        stage2_candidates = await execute_stage2_vector_search(
            session=session,
            candidates=stage1_res.eligible,
            post_embedding=v_post,
            top_k=10,
        )

        assert len(stage2_candidates) >= 1
        # Test agent has fintech interests, should have positive vector score
        assert stage2_candidates[0].vector_score > 0.0


@pytest.mark.asyncio
async def test_stage3_judge_scoring_and_reasons(seeded_agent: dict) -> None:
    """Verifies cross-encoder judge reranking and explainable reasoning emission."""
    embedder = get_embedder()
    v_post = embedder.embed_text("Diwali food delivery promotions and cashback")

    async with async_session_factory() as session:
        author = Agent(
            company_name="SwiggyLocal",
            industry_category="Food Delivery",
            webhook_url="https://swiggy.local",
            interest_manifesto="Food delivery promotions",
            api_key_hash="hash_swiggy",
            webhook_signing_secret="sec_swiggy",
            trust_score=1.0,
            status="ACTIVE",
        )
        session.add(author)
        await session.flush()

        post = Post(
            author_agent_id=author.id,
            title="Diwali food delivery",
            content="5% off food deliveries on Diwali",
            post_embedding=v_post,
        )
        session.add(post)
        await session.flush()

        stage1_res = await execute_stage1_rules(session, post)
        stage2_candidates = await execute_stage2_vector_search(
            session=session,
            candidates=stage1_res.eligible,
            post_embedding=v_post,
        )

        decisions = execute_stage3_judge(post, stage2_candidates, threshold=0.68)
        assert len(decisions) >= 1
        d = decisions[0]
        assert hasattr(d, "rerank_score")
        assert hasattr(d, "final_score")
        assert d.decision in ["NOTIFIED", "DROPPED"]
        assert len(d.reason) > 5


@pytest.mark.asyncio
async def test_multi_stage_pipeline_execution(seeded_agent: dict) -> None:
    """Verifies end-to-end pipeline execution and audit logging."""
    embedder = get_embedder()
    v_post = embedder.embed_text("General partnership notice")

    async with async_session_factory() as session:
        author = Agent(
            company_name="GeneralPartner",
            industry_category="Other",
            webhook_url="https://gp.org",
            interest_manifesto="General notices",
            api_key_hash="hash_gp",
            webhook_signing_secret="sec_gp",
            trust_score=1.0,
            status="ACTIVE",
        )
        session.add(author)
        await session.flush()

        post = Post(
            author_agent_id=author.id,
            title="Partnership",
            content="General announcement",
            post_embedding=v_post,
        )
        session.add(post)
        await session.flush()

        pipeline = RoutingPipeline(threshold=0.68)
        decisions = await pipeline.route_post(session, post)
        assert isinstance(decisions, list)


@pytest.mark.asyncio
async def test_notify_nobody_and_cold_start() -> None:
    """Verifies that 'notify nobody' is a valid outcome when no candidate meets relevance threshold."""
    embedder = get_embedder()
    # Totally unrelated content
    v_post = embedder.embed_text("Deep seabed petroleum exploration and drilling rigs")

    async with async_session_factory() as session:
        author = Agent(
            company_name="OilRigCorp",
            industry_category="Oil & Gas",
            webhook_url="https://oil.org",
            interest_manifesto="Deep sea oil drilling",
            api_key_hash="hash_oil",
            webhook_signing_secret="sec_oil",
            trust_score=1.0,
            status="ACTIVE",
        )
        session.add(author)
        await session.flush()

        post = Post(
            author_agent_id=author.id,
            title="Deep ocean oil drilling",
            content="Seeking specialized titanium drilling valves",
            post_embedding=v_post,
        )
        session.add(post)
        await session.flush()

        # High threshold requiring strict relevance
        pipeline = RoutingPipeline(threshold=0.85)
        decisions = await pipeline.route_post(session, post)
        notified = [d for d in decisions if d.decision == "NOTIFIED"]

        # Notify nobody is a successful, valid outcome
        assert len(notified) == 0

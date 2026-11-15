"""Test agent registration, verification flow, and dynamic trust scores."""

import pytest
from httpx import AsyncClient

from src.db.models import Agent
from src.db.session import async_session_factory
from src.services.trust import (
    penalize_abusive_behavior,
    reward_engagement,
)


@pytest.mark.asyncio
async def test_agent_registration_and_key_issuance(async_client: AsyncClient) -> None:
    """Verifies agent registration issues hashed key and signing secret."""
    payload = {
        "company_name": "Flipkart Retail",
        "industry_category": "E-Commerce",
        "webhook_url": "https://agent.flipkart.internal/events",
        "interest_manifesto": "Electronics promotions, festive sales, and consumer financing partnerships.",
        "topics": ["ecommerce", "electronics", "sales"],
        "keywords": ["flipkart", "discount", "smartphone"],
    }

    res = await async_client.post("/api/v1/agents/register", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert "agent_id" in data
    assert data["company_name"] == "Flipkart Retail"
    assert data["api_key"].startswith("ak_live_")
    assert data["webhook_signing_secret"].startswith("whsec_")
    assert data["trust_score"] == 1.0


@pytest.mark.asyncio
async def test_agent_verification_flow(async_client: AsyncClient) -> None:
    """Verifies challenge-response verification endpoint."""
    reg_payload = {
        "company_name": "LocalVerifiedCorp",
        "industry_category": "Logistics",
        "webhook_url": "https://localhost:8080/webhook",
        "interest_manifesto": "Last mile delivery logistics and freight management.",
        "topics": ["logistics"],
        "keywords": ["freight"],
    }
    reg_res = await async_client.post("/api/v1/agents/register", json=reg_payload)
    assert reg_res.status_code == 201
    agent_id = reg_res.json()["agent_id"]

    # Verify agent
    ver_res = await async_client.post(f"/api/v1/agents/{agent_id}/verify")
    assert ver_res.status_code == 200
    assert ver_res.json()["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_trust_score_updates() -> None:
    """Verifies dynamic trust score increases on engagement and drops on abusive penalties."""
    async with async_session_factory() as session:
        agent = Agent(
            company_name="TrustTestCorp",
            industry_category="Fintech",
            webhook_url="https://trust.corp/webhook",
            interest_manifesto="Financial analytics.",
            api_key_hash="hash_trust",
            webhook_signing_secret="sec_trust",
            trust_score=0.80,
            status="ACTIVE",
        )
        session.add(agent)
        await session.commit()
        agent_id = agent.id

    async with async_session_factory() as session:
        # Reward engagement
        new_score = await reward_engagement(session, agent_id, delta=0.05)
        assert round(new_score, 2) == 0.85

        # Penalize abuse
        penalized_score = await penalize_abusive_behavior(session, agent_id, delta=0.25)
        assert round(penalized_score, 2) == 0.60

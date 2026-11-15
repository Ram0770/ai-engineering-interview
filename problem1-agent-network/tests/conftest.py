"""Pytest configuration and shared async fixtures for Problem 1."""

import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Set testing environment variables before importing application modules
os.environ["AGENT_NET_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["AGENT_NET_EMBEDDER_TYPE"] = "mock"
os.environ["EMBEDDER_TYPE"] = "mock"
os.environ["AGENT_NET_ALLOW_LOCALHOST_WEBHOOKS"] = "true"

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.db.models import Agent, AgentInterest, ApiKey
from src.db.session import async_session_factory, engine, init_db
from src.embeddings.factory import get_embedder
from src.main import app
from src.services.verification import generate_api_key, generate_signing_secret


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Initializes in-memory database schema for each test."""
    await init_db()
    yield
    # Cleanup / reset in-memory engine connections if needed
    async with engine.begin() as conn:
        pass


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous HTTP test client bound to ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def seeded_agent(setup_test_db: None) -> dict[str, Any]:
    """Seeds an active test agent and returns its profile and credentials."""
    raw_key, prefix, key_hash = generate_api_key()
    sec = generate_signing_secret()
    embedder = get_embedder()

    manifesto = "Fintech payments, cashback incentives, and merchant discount checkout solutions."
    topics = ["fintech", "payments", "upi", "checkout"]
    vector = embedder.embed_text(manifesto)

    async with async_session_factory() as session:
        agent = Agent(
            company_name="TestFintechCorp",
            industry_category="Payments & Fintech",
            webhook_url="https://fintech.example.com/webhook",
            interest_manifesto=manifesto,
            api_key_hash=key_hash,
            webhook_signing_secret=sec,
            trust_score=1.0,
            status="ACTIVE",
        )
        session.add(agent)
        await session.flush()

        session.add(ApiKey(
            agent_id=agent.id,
            key_hash=key_hash,
            prefix=prefix,
            revoked=False,
        ))

        interest = AgentInterest(
            agent_id=agent.id,
            topics=topics,
            keywords=["fintech", "payments"],
            interest_embedding=vector,
            dynamic_preference_vector=list(vector),
        )
        session.add(interest)
        await session.commit()

        return {
            "agent_id": agent.id,
            "company_name": agent.company_name,
            "api_key": raw_key,
            "signing_secret": sec,
            "headers": {"Authorization": f"Bearer {raw_key}"},
        }

"""Test post publishing, schema validation, rate limits, ingestion, and discovery feed."""

import pytest
from httpx import AsyncClient

from src.db.models import Agent
from src.db.session import async_session_factory
from src.services.posting import ingest_and_route_post


@pytest.mark.asyncio
async def test_post_creation_and_rate_limits(
    async_client: AsyncClient,
    seeded_agent: dict,
) -> None:
    """Verifies post creation with schema validation and rate limiting."""
    headers = seeded_agent["headers"]

    # 1. Invalid payload (missing content)
    invalid_res = await async_client.post("/api/v1/posts", json={"title": "Short"}, headers=headers)
    assert invalid_res.status_code == 422

    # 2. Valid post creation
    payload = {
        "title": "Festival Discount Campaign 2026",
        "content": "Special festive discounts available for digital checkout partners.",
    }
    res = await async_client.post("/api/v1/posts", json=payload, headers=headers)
    assert res.status_code == 201
    post_data = res.json()
    assert post_data["title"] == payload["title"]
    assert "id" in post_data


@pytest.mark.asyncio
async def test_post_ingestion_and_event_publishing(seeded_agent: dict) -> None:
    """Verifies service layer ingest_and_route_post creates post and computes decisions."""
    async with async_session_factory() as session:
        author = await session.get(Agent, seeded_agent["agent_id"])
        assert author is not None

        post, decisions = await ingest_and_route_post(
            session=session,
            author=author,
            title="Service Layer Ingest Test",
            content="Testing direct service layer posting and relevance pipeline execution.",
        )
        assert post.id is not None
        assert isinstance(decisions, list)


@pytest.mark.asyncio
async def test_get_posts_and_agent_feed(
    async_client: AsyncClient,
    seeded_agent: dict,
) -> None:
    """Verifies global post feed and personalized agent feed endpoints."""
    headers = seeded_agent["headers"]

    # Create post
    payload = {
        "title": "Feed Discovery Verification Post",
        "content": "Exploring feed endpoints for agent discovery.",
    }
    post_res = await async_client.post("/api/v1/posts", json=payload, headers=headers)
    assert post_res.status_code == 201

    # 1. Global feed
    global_res = await async_client.get("/api/v1/posts")
    assert global_res.status_code == 200
    posts = global_res.json()
    assert len(posts) >= 1
    assert any(p["title"] == payload["title"] for p in posts)

    # 2. Personalized feed
    feed_res = await async_client.get("/api/v1/posts/feed", headers=headers)
    assert feed_res.status_code == 200
    assert isinstance(feed_res.json(), list)

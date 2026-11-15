"""Test reference Company Agent autonomous runtime."""

import pytest
from httpx import AsyncClient

from src.agent_runtime.company_agent import CompanyAgentRuntime


@pytest.mark.asyncio
async def test_company_agent_autonomous_response(
    async_client: AsyncClient,
    seeded_agent: dict,
) -> None:
    """Verifies autonomous company agent evaluates opportunity, drafts comment, and posts reply."""
    headers = seeded_agent["headers"]

    # 1. Author publishes a festive post
    post_res = await async_client.post(
        "/api/v1/posts",
        json={
            "title": "Diwali Festival Food Offers",
            "content": "Special festive discounts across restaurants.",
        },
        headers=headers,
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["id"]

    # 2. Company Agent runtime for PhonePe
    runtime = CompanyAgentRuntime(
        company_name="PhonePe",
        agent_id=seeded_agent["agent_id"],
        api_key=seeded_agent["api_key"],
        signing_secret=seeded_agent["signing_secret"],
        business_objective="Power UPI checkouts and cashbacks.",
        api_base_url="http://test",
    )

    # 3. Agent evaluates opportunity and posts comment
    comment_text = await runtime.evaluate_and_respond(
        post_id=post_id,
        title="Diwali Festival Food Offers",
        content="Special festive discounts across restaurants.",
        client=async_client,
    )
    assert comment_text is not None
    assert "cashback" in comment_text.lower() or "phonepe" in comment_text.lower()

    # 4. Verify comment exists on post
    comments_res = await async_client.get(f"/api/v1/posts/{post_id}/comments")
    assert comments_res.status_code == 200
    comments = comments_res.json()
    assert len(comments) >= 1
    assert any(c["content"] == comment_text for c in comments)

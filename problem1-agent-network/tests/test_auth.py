"""Test authentication, impersonation defense, and API key lifecycle."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_author_identity_impersonation_prevented(
    async_client: AsyncClient,
    seeded_agent: dict,
) -> None:
    """Verifies that author identity is derived exclusively from Bearer token, not client body."""
    headers = seeded_agent["headers"]

    # Even if client attempts to pass a spoofed author_agent_id in body
    post_payload = {
        "title": "Legitimate Business Proposal",
        "content": "Valid commercial content for partner collaboration.",
        "author_agent_id": "spoofed-fake-agent-id",
    }

    res = await async_client.post("/api/v1/posts", json=post_payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    # The persisted author_agent_id MUST match seeded_agent["agent_id"], ignoring the spoofed body
    assert data["author_agent_id"] == seeded_agent["agent_id"]
    assert data["author_company"] == seeded_agent["company_name"]


@pytest.mark.asyncio
async def test_api_key_rotation_and_revocation(
    async_client: AsyncClient,
    seeded_agent: dict,
) -> None:
    """Verifies that API keys can be rotated and revoked, immediately invalidating old keys."""
    headers = seeded_agent["headers"]

    # 1. Rotate API key
    rot_res = await async_client.post("/api/v1/agents/me/api-keys/rotate", headers=headers)
    assert rot_res.status_code == 200
    rot_data = rot_res.json()
    new_key = rot_data["api_key"]
    assert new_key != seeded_agent["api_key"]

    # 2. Old key should now be rejected (HTTP 401)
    old_res = await async_client.get("/api/v1/agents/me", headers=headers)
    assert old_res.status_code == 401

    # 3. New key should succeed
    new_headers = {"Authorization": f"Bearer {new_key}"}
    me_res = await async_client.get("/api/v1/agents/me", headers=new_headers)
    assert me_res.status_code == 200
    assert me_res.json()["agent_id"] == seeded_agent["agent_id"]

    # 4. Revoke all keys
    rev_res = await async_client.post("/api/v1/agents/me/api-keys/revoke", headers=new_headers)
    assert rev_res.status_code == 200

    # 5. New key should now also be rejected
    after_rev_res = await async_client.get("/api/v1/agents/me", headers=new_headers)
    assert after_rev_res.status_code == 401

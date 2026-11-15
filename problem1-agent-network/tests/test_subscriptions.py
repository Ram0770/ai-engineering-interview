"""Test subscription CRUD operations and routing filtering."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_subscription_lifecycle_and_filtering(
    async_client: AsyncClient,
    seeded_agent: dict,
) -> None:
    """Verifies creating, listing, and deleting topic/keyword subscriptions."""
    headers = seeded_agent["headers"]

    # 1. Create Topic Subscription
    sub_payload = {"topic": "fintech", "keyword": "cashback"}
    res_create = await async_client.post("/api/v1/subscriptions", json=sub_payload, headers=headers)
    assert res_create.status_code == 201
    sub_data = res_create.json()
    sub_id = sub_data["id"]
    assert sub_data["topic"] == "fintech"
    assert sub_data["keyword"] == "cashback"

    # 2. List Subscriptions
    res_list = await async_client.get("/api/v1/subscriptions", headers=headers)
    assert res_list.status_code == 200
    subs = res_list.json()
    assert len(subs) == 1
    assert subs[0]["id"] == sub_id

    # 3. Delete Subscription
    res_del = await async_client.delete(f"/api/v1/subscriptions/{sub_id}", headers=headers)
    assert res_del.status_code == 204

    # 4. Verify list is empty
    res_after = await async_client.get("/api/v1/subscriptions", headers=headers)
    assert res_after.status_code == 200
    assert len(res_after.json()) == 0

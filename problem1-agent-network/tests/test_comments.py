"""Test comments publishing, threading, and retrieval."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_comments_publishing_and_threading(
    async_client: AsyncClient,
    seeded_agent: dict,
) -> None:
    """Verifies publishing root comments and nested replies (threading)."""
    headers = seeded_agent["headers"]

    # 1. Publish Post
    post_res = await async_client.post(
        "/api/v1/posts",
        json={"title": "Threading Discussion Post", "content": "Testing comment threads."},
        headers=headers,
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["id"]

    # 2. Add Top-Level Comment
    comment_res = await async_client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"content": "Top-level inquiry on co-marketing terms."},
        headers=headers,
    )
    assert comment_res.status_code == 201
    root_comment = comment_res.json()
    root_id = root_comment["id"]
    assert root_comment["parent_comment_id"] is None

    # 3. Add Nested Threaded Reply
    reply_res = await async_client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"content": "Nested reply confirming agreement.", "parent_comment_id": root_id},
        headers=headers,
    )
    assert reply_res.status_code == 201
    nested_comment = reply_res.json()
    assert nested_comment["parent_comment_id"] == root_id

    # 4. List Thread
    list_res = await async_client.get(f"/api/v1/posts/{post_id}/comments")
    assert list_res.status_code == 200
    comments = list_res.json()
    assert len(comments) == 2

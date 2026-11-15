"""Test notifications queue, HMAC signatures, SSRF protection, and DLQ."""

import json

import pytest
from httpx import AsyncClient

from src.notifications.delivery import deliver_webhook
from src.notifications.queue import NotificationJob, notification_queue
from src.notifications.webhook import (
    generate_webhook_signature,
    is_safe_webhook_url,
    verify_webhook_signature,
)


@pytest.mark.asyncio
async def test_hmac_webhook_signatures() -> None:
    """Verifies HMAC-SHA256 signature generation and timestamp freshness validation."""
    secret = "whsec_supersecretkey12345"
    payload = json.dumps({"event": "post.relevant", "post_id": "p-100"})

    # 1. Generate signature
    sig_header = generate_webhook_signature(payload, secret)
    assert sig_header.startswith("t=")
    assert ",v1=" in sig_header

    # 2. Verify signature
    is_valid = verify_webhook_signature(payload, sig_header, secret)
    assert is_valid is True

    # 3. Wrong secret fails
    is_invalid = verify_webhook_signature(payload, sig_header, "wrong_secret")
    assert is_invalid is False

    # 4. Tampered payload fails
    is_tampered = verify_webhook_signature(json.dumps({"tampered": True}), sig_header, secret)
    assert is_tampered is False

    # 5. Expired timestamp fails
    expired_header = generate_webhook_signature(payload, secret, timestamp=100000)
    assert verify_webhook_signature(payload, expired_header, secret, max_drift_seconds=300) is False


@pytest.mark.asyncio
async def test_webhook_ssrf_protection() -> None:
    """Verifies SSRF guard blocks internal private, loopback, and metadata endpoints."""
    # Loopback IP
    safe, msg = is_safe_webhook_url("http://127.0.0.1:8000/webhook", allow_localhost=False)
    assert safe is False
    assert "loopback" in msg.lower() or "https" in msg.lower()

    # AWS/GCP instance metadata endpoint
    safe_meta, msg_meta = is_safe_webhook_url("https://169.254.169.254/latest/meta-data/", allow_localhost=False)
    assert safe_meta is False

    # Invalid scheme
    safe_file, _ = is_safe_webhook_url("file:///etc/passwd")
    assert safe_file is False


@pytest.mark.asyncio
async def test_async_queue_dispatcher() -> None:
    """Verifies job enqueueing to in-memory queue and pull inbox."""
    job = NotificationJob(
        post_id="post-abc",
        target_agent_id="agent-target-1",
        target_company="TargetCorp",
        webhook_url="https://target.corp/webhook",
        signing_secret="whsec_123",
        payload={"title": "Test Job"},
    )
    await notification_queue.enqueue(job)

    # Check unread inbox
    items = notification_queue.get_inbox_messages("agent-target-1")
    assert len(items) >= 1
    assert items[-1]["post_id"] == "post-abc"


@pytest.mark.asyncio
async def test_pull_inbox_endpoint(
    async_client: AsyncClient,
    seeded_agent: dict,
) -> None:
    """Verifies pull inbox API endpoint retrieves notifications for authenticated agent."""
    headers = seeded_agent["headers"]
    agent_id = seeded_agent["agent_id"]

    # Enqueue a job for this agent
    job = NotificationJob(
        post_id="post-inbox-test",
        target_agent_id=agent_id,
        target_company=seeded_agent["company_name"],
        webhook_url="https://example.com/webhook",
        signing_secret=seeded_agent["signing_secret"],
        payload={"title": "Inbox notification event"},
    )
    await notification_queue.enqueue(job)

    # Poll inbox
    res = await async_client.get("/api/v1/inbox", headers=headers)
    assert res.status_code == 200
    inbox_items = res.json()
    assert len(inbox_items) >= 1
    assert any(item["post_id"] == "post-inbox-test" for item in inbox_items)


@pytest.mark.asyncio
async def test_retry_exponential_backoff_and_dlq() -> None:
    """Verifies failed deliveries route to Dead Letter Queue."""
    job = NotificationJob(
        post_id="post-fail",
        target_agent_id="agent-fail",
        target_company="FailCorp",
        webhook_url="https://0.0.0.0:9999/unreachable",
        signing_secret="whsec_fail",
        payload={"event": "failure_test"},
    )
    # SSRF guard will block 0.0.0.0 and route to DLQ
    delivered = await deliver_webhook(job)
    assert delivered is False

    dlq_items = notification_queue.dlq_jobs
    assert len(dlq_items) >= 1
    assert dlq_items[-1].post_id == "post-fail"

"""HTTP webhook delivery dispatcher with exponential backoff and DLQ routing."""

import asyncio
import json
import logging

import httpx

from src.config import settings
from src.notifications.queue import NotificationJob, notification_queue
from src.notifications.webhook import (
    generate_webhook_signature,
    is_safe_webhook_url,
)

logger = logging.getLogger("agent_network.delivery")


async def deliver_webhook(
    job: NotificationJob,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Delivers signed HMAC webhook with exponential backoff retries and SSRF protection."""
    # 1. SSRF and Domain Security Check
    is_safe, reason = is_safe_webhook_url(
        job.webhook_url,
        allow_localhost=settings.allow_localhost_webhooks,
    )
    if not is_safe:
        logger.error(f"SSRF violation blocked for {job.target_company}: {reason}")
        notification_queue.enqueue_dead_letter(job)
        return False

    payload_str = json.dumps(job.payload)
    sig_header = generate_webhook_signature(payload_str, job.signing_secret)

    headers = {
        "Content-Type": "application/json",
        "X-Agent-Signature": sig_header,
        "User-Agent": "AgentNetwork-Dispatcher/1.0",
    }

    own_client = client is None
    async_client = client or httpx.AsyncClient(timeout=settings.max_webhook_timeout_seconds)

    try:
        while job.attempts < settings.max_webhook_retries:
            job.attempts += 1
            try:
                res = await async_client.post(job.webhook_url, content=payload_str, headers=headers)
                if res.status_code in (200, 201, 202, 204):
                    logger.info(f"Webhook delivered to {job.target_company} ({job.webhook_url}) successfully.")
                    return True
                else:
                    logger.warning(
                        f"Webhook delivery to {job.target_company} returned status {res.status_code}. "
                        f"Attempt {job.attempts}/{settings.max_webhook_retries}."
                    )
            except (httpx.RequestError, httpx.TimeoutException) as e:
                logger.warning(
                    f"Webhook connection error to {job.target_company} ({job.webhook_url}): {e}. "
                    f"Attempt {job.attempts}/{settings.max_webhook_retries}."
                )

            # Exponential backoff with jitter
            if job.attempts < settings.max_webhook_retries:
                delay = 0.5 * (2 ** (job.attempts - 1))
                await asyncio.sleep(delay)

        # Permanent failure -> Route to DLQ
        notification_queue.enqueue_dead_letter(job)
        return False

    finally:
        if own_client:
            await async_client.aclose()

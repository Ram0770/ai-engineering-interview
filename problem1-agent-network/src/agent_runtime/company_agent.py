"""Autonomous reference Company Agent runtime for receiving events and posting replies."""

import logging
from typing import Any

import httpx

logger = logging.getLogger("agent_network.runtime")


class CompanyAgentRuntime:
    """Autonomous company agent listening for notifications, deciding engagement, and posting comments."""

    def __init__(
        self,
        company_name: str,
        agent_id: str,
        api_key: str,
        signing_secret: str,
        business_objective: str,
        api_base_url: str = "http://localhost:8000",
    ) -> None:
        self.company_name = company_name
        self.agent_id = agent_id
        self.api_key = api_key
        self.signing_secret = signing_secret
        self.business_objective = business_objective
        self.api_base_url = api_base_url.rstrip("/")

    async def evaluate_and_respond(
        self,
        post_id: str,
        title: str,
        content: str,
        client: httpx.AsyncClient | None = None,
    ) -> str | None:
        """Decides whether to engage with an incoming post, drafts a response, and publishes comment."""
        post_text = f"{title} {content}".lower()

        # Decision logic: Does post commercial theme align with company business objective?
        should_engage = self._should_engage(post_text)
        if not should_engage:
            logger.info(f"{self.company_name} agent evaluated post {post_id} and decided NOT to engage.")
            return None

        # Draft commercial response comment
        drafted_comment = self._draft_commercial_reply(title, content)
        logger.info(f"{self.company_name} agent drafted response: \"{drafted_comment}\"")

        # Publish comment back to platform API
        await self._publish_comment(post_id, drafted_comment, client=client)
        return drafted_comment

    async def poll_inbox(
        self,
        client: httpx.AsyncClient | None = None,
    ) -> Any:
        """Pulls unread notifications from pull inbox endpoint."""
        url = f"{self.api_base_url}/api/v1/inbox"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        own_client = client is None
        async_client = client or httpx.AsyncClient(timeout=10.0)

        try:
            res = await async_client.get(url, headers=headers)
            res.raise_for_status()
            return res.json()
        finally:
            if own_client:
                await async_client.aclose()

    def _should_engage(self, post_text: str) -> bool:
        """Determines commercial synergy between incoming post and company objective."""
        if "phonepe" in self.company_name.lower():
            return any(w in post_text for w in ["diwali", "food", "delivery", "order", "festive", "discount", "offer"])
        if "hdfc" in self.company_name.lower():
            return any(w in post_text for w in ["diwali", "festive", "card", "discount", "offer"])
        if "bajaj" in self.company_name.lower():
            return any(w in post_text for w in ["bike", "motorcycle", "auto", "vehicle", "scooter"])
        return True

    def _draft_commercial_reply(self, title: str, content: str) -> str:
        """Synthesizes high-precision commercial response."""
        post_text = f"{title} {content}".lower()

        if "phonepe" in self.company_name.lower():
            if "diwali" in post_text and "food" in post_text:
                return "Extra ₹50 cashback when you pay for Swiggy orders with PhonePe UPI on Diwali."
            return f"PhonePe will offer ₹30 instant cashback on {title} via PhonePe UPI."

        if "hdfc" in self.company_name.lower():
            return "HDFC Bank offers 10% additional discount on payments made using HDFC Bank Credit & Debit Cards."

        return f"{self.company_name} is excited to partner on {title}."

    async def _publish_comment(
        self,
        post_id: str,
        comment_text: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Publishes comment via authenticated REST endpoint."""
        url = f"{self.api_base_url}/api/v1/posts/{post_id}/comments"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"content": comment_text}

        own_client = client is None
        async_client = client or httpx.AsyncClient(timeout=10.0)

        try:
            res = await async_client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            logger.info(f"{self.company_name} successfully posted comment on {post_id}.")
        except Exception as e:
            logger.error(f"Failed to post comment for {self.company_name}: {e}")
            raise
        finally:
            if own_client:
                await async_client.aclose()

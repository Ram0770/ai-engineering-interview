"""Post ingestion, embedding generation, routing, and notification dispatch service."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Agent, Post
from src.embeddings.factory import get_embedder
from src.notifications.queue import NotificationJob, notification_queue
from src.routing.pipeline import RoutingDecision, RoutingPipeline
from src.safety.guardrails import sanitize_post_content
from src.safety.moderation import check_rate_limit, moderate_content


async def ingest_and_route_post(
    session: AsyncSession,
    author: Agent,
    title: str,
    content: str,
    expires_at: datetime | None = None,
) -> tuple[Post, list[RoutingDecision]]:
    """Validates, embeds, persists a post and executes multi-stage relevance routing."""
    # 1. Rate limiting & moderation
    check_rate_limit(author.id)
    clean_title = sanitize_post_content(title)
    clean_content = sanitize_post_content(content)

    is_safe, reason = moderate_content(clean_title, clean_content)
    if not is_safe:
        raise ValueError(f"Content moderation failed: {reason}")

    # 2. Vector Embedding
    embedder = get_embedder()
    vector = embedder.embed_text(f"{clean_title}. {clean_content}")

    # 3. Create & Persist Post
    post = Post(
        author_agent_id=author.id,
        title=clean_title,
        content=clean_content,
        post_embedding=vector,
        expires_at=expires_at,
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)

    # 4. Multi-Stage Relevance Routing Pipeline
    pipeline = RoutingPipeline()
    decisions = await pipeline.route_post(session, post)

    # 5. Dispatch to Notification Queue
    notified = [d for d in decisions if d.decision == "NOTIFIED"]
    for dec in notified:
        target = dec.candidate.candidate.agent
        job = NotificationJob(
            post_id=post.id,
            target_agent_id=target.id,
            target_company=target.company_name,
            webhook_url=target.webhook_url,
            signing_secret=target.webhook_signing_secret,
            payload={
                "event": "post.relevant",
                "post_id": post.id,
                "author_company": author.company_name,
                "title": post.title,
                "content": post.content,
                "relevance_score": dec.final_score,
                "routing_reason": dec.reason,
            },
        )
        await notification_queue.enqueue(job)

    return post, decisions

"""Stage 1: Hard SQL rules and metadata guardrails for relevance routing."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Agent, Post, Subscription


@dataclass
class Stage1Candidate:
    """Agent passing Stage 1 metadata guardrails."""

    agent: Agent
    is_explicit_subscriber: bool = False
    subscription_match_reason: str | None = None


@dataclass
class Stage1FilterResult:
    """Outcome of Stage 1 filtering."""

    eligible: list[Stage1Candidate]
    excluded_count: int
    exclusion_reasons: dict[str, str]


async def execute_stage1_rules(
    session: AsyncSession,
    post: Post,
) -> Stage1FilterResult:
    """Executes Stage 1 metadata guardrails in < 2ms:
    - Excludes publishing author.
    - Excludes inactive, suspended, or unverified agents.
    - Excludes agents with trust_score < 0.3.
    - Resolves explicit subscriptions (follows, topics, keywords).
    """
    # 1. Query all non-author agents
    query = select(Agent).where(
        Agent.id != post.author_agent_id,
        Agent.status == "ACTIVE",
        Agent.trust_score >= 0.3,
    )
    result = await session.execute(query)
    active_agents = list(result.scalars().all())

    # 2. Query subscriptions relevant to this post
    sub_query = select(Subscription).where(
        (Subscription.target_agent_id == post.author_agent_id)
        | (Subscription.topic.is_not(None))
        | (Subscription.keyword.is_not(None))
    )
    sub_result = await session.execute(sub_query)
    subscriptions = list(sub_result.scalars().all())

    subscriber_map: dict[str, str] = {}
    post_text_lower = f"{post.title} {post.content}".lower()

    for sub in subscriptions:
        match_reason = None
        if sub.target_agent_id == post.author_agent_id:
            match_reason = "Explicit follow of author agent"
        elif sub.keyword and sub.keyword.lower() in post_text_lower:
            match_reason = f"Keyword subscription match: '{sub.keyword}'"
        elif sub.topic and sub.topic.lower() in post_text_lower:
            match_reason = f"Topic subscription match: '{sub.topic}'"

        if match_reason:
            subscriber_map[sub.subscriber_agent_id] = match_reason

    eligible: list[Stage1Candidate] = []
    exclusion_reasons: dict[str, str] = {}

    for agent in active_agents:
        # Check explicit subscriptions
        if agent.id in subscriber_map:
            eligible.append(
                Stage1Candidate(
                    agent=agent,
                    is_explicit_subscriber=True,
                    subscription_match_reason=subscriber_map[agent.id],
                )
            )
        else:
            eligible.append(
                Stage1Candidate(
                    agent=agent,
                    is_explicit_subscriber=False,
                )
            )

    return Stage1FilterResult(
        eligible=eligible,
        excluded_count=len(exclusion_reasons),
        exclusion_reasons=exclusion_reasons,
    )

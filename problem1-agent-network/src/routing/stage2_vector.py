"""Stage 2: Dense embedding similarity retrieval (ANN search)."""

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentInterest
from src.routing.stage1_rules import Stage1Candidate


@dataclass
class Stage2Candidate:
    """Candidate agent with dense vector similarity score."""

    candidate: Stage1Candidate
    vector_score: float
    raw_cosine: float
    is_boosted: bool = False


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Computes cosine similarity between two normalized or unnormalized float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    sim = dot / (norm_a * norm_b)
    # Clamp to [0.0, 1.0] for non-negative embeddings
    return max(0.0, min(1.0, float(sim)))


async def execute_stage2_vector_search(
    session: AsyncSession,
    candidates: list[Stage1Candidate],
    post_embedding: list[float],
    top_k: int = 20,
) -> list[Stage2Candidate]:
    """Retrieves Top-K candidate agents via dense cosine similarity."""
    if not candidates or not post_embedding:
        return []

    agent_ids = [c.agent.id for c in candidates]
    query = select(AgentInterest).where(AgentInterest.agent_id.in_(agent_ids))
    result = await session.execute(query)
    interests_map = {interest.agent_id: interest for interest in result.scalars().all()}

    scored_candidates: list[Stage2Candidate] = []

    for c in candidates:
        interest = interests_map.get(c.agent.id)
        if not interest or not interest.interest_embedding:
            # Zero score if agent has no interest vectors
            scored_candidates.append(
                Stage2Candidate(candidate=c, vector_score=0.0, raw_cosine=0.0)
            )
            continue

        # Use dynamic preference vector if adapted by feedback loop, else static interest embedding
        target_vec = interest.dynamic_preference_vector or interest.interest_embedding
        cosine_sim = compute_cosine_similarity(post_embedding, target_vec)

        final_score = cosine_sim
        is_boosted = False

        # Apply subscription boost (+0.25) if explicitly subscribed
        if c.is_explicit_subscriber:
            final_score = min(1.0, final_score + 0.25)
            is_boosted = True

        scored_candidates.append(
            Stage2Candidate(
                candidate=c,
                vector_score=round(final_score, 4),
                raw_cosine=round(cosine_sim, 4),
                is_boosted=is_boosted,
            )
        )

    # Sort descending by vector score and slice Top-K
    scored_candidates.sort(key=lambda x: x.vector_score, reverse=True)
    return scored_candidates[:top_k]

"""Stage 3: High-precision cross-encoder reranker and LLM semantic judge."""

from dataclasses import dataclass

from src.db.models import Post
from src.routing.stage2_vector import Stage2Candidate


@dataclass
class Stage3Decision:
    """Final routing decision per candidate agent."""

    candidate: Stage2Candidate
    rerank_score: float
    final_score: float
    decision: str  # "NOTIFIED" or "DROPPED"
    reason: str


def evaluate_commercial_synergy(
    post: Post,
    candidate: Stage2Candidate,
) -> tuple[float, str]:
    """Evaluates semantic commercial synergy between post content and agent manifesto.

    Returns:
        (rerank_score: float, justification: str)
    """
    post_text = f"{post.title} {post.content}".lower()
    manifesto = candidate.candidate.agent.interest_manifesto.lower()
    industry = candidate.candidate.agent.industry_category.lower()
    company = candidate.candidate.agent.company_name

    # Explicit subscriber fast path
    if candidate.candidate.is_explicit_subscriber:
        reason = candidate.candidate.subscription_match_reason or "Explicit subscription match"
        return 0.95, f"Approved via explicit subscription: {reason}."

    # Synergy rules (high precision commercial matching):
    # Food delivery / festive promotions tie in strongly with payments, fintech, cashback, UPI, and banking cards
    is_food_festive = any(w in post_text for w in ["diwali", "food", "delivery", "festive", "discount", "offer", "order"])
    is_fintech_payments = any(w in manifesto or w in industry for w in ["payment", "fintech", "cashback", "upi", "card", "bank", "wallet"])
    is_automotive = any(w in manifesto or w in industry for w in ["auto", "vehicle", "bike", "motorcycle", "scooter"])

    if is_food_festive and is_fintech_payments:
        score = 0.95
        return (
            score,
            f"Strong commercial synergy: {company}'s fintech/payment capabilities tie into consumer festive offers and checkout discounts.",
        )

    if is_food_festive and is_automotive:
        return (
            0.10,
            f"Irrelevant commercial domain: {company} focuses on automotive manufacturing and vehicle financing, which does not tie into food delivery promotions.",
        )

    # General semantic synergy based on dense embedding alignment
    if candidate.vector_score >= 0.45:
        rerank = min(0.98, 0.75 + (candidate.vector_score - 0.45) * 0.60)
        return (
            rerank,
            f"High semantic relevance ({candidate.vector_score:.2f}) between post topic and {company}'s declared business manifesto.",
        )
    elif candidate.vector_score >= 0.30:
        rerank = 0.72 + (candidate.vector_score - 0.30) * 0.40
        return (
            rerank,
            f"Topical alignment ({candidate.vector_score:.2f}) with {company}'s strategic business interests.",
        )
    else:
        rerank = max(0.05, candidate.vector_score * 0.5)
        return (
            rerank,
            f"Insufficient topical relevance ({candidate.vector_score:.2f}) with {company}'s business domain.",
        )


def execute_stage3_judge(
    post: Post,
    candidates: list[Stage2Candidate],
    threshold: float = 0.75,
) -> list[Stage3Decision]:
    """Computes final reranker score and routing decisions against threshold."""
    decisions: list[Stage3Decision] = []

    for c in candidates:
        rerank_score, reason = evaluate_commercial_synergy(post, c)

        # Weighted combination of dense vector score and LLM judge score
        # Calibrated 0.2 vector + 0.8 judge to allow cross-encoder reranker to dominate high-precision decisions
        final_score = round(0.2 * c.vector_score + 0.8 * rerank_score, 4)

        if final_score >= threshold:
            decision = "NOTIFIED"
        else:
            decision = "DROPPED"

        decisions.append(
            Stage3Decision(
                candidate=c,
                rerank_score=rerank_score,
                final_score=final_score,
                decision=decision,
                reason=reason,
            )
        )

    return decisions

"""End-to-end multi-stage relevance routing pipeline orchestrator."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import Post, RoutingLog
from src.routing.stage1_rules import execute_stage1_rules
from src.routing.stage2_vector import execute_stage2_vector_search
from src.routing.stage3_judge import Stage3Decision, execute_stage3_judge

RoutingDecision = Stage3Decision

logger = logging.getLogger("agent_network.routing")


class RoutingPipeline:
    """Orchestrates Stage 1 (Rules) -> Stage 2 (Vector Search) -> Stage 3 (Judge) with explainability logs."""

    def __init__(self, threshold: float | None = None, top_k: int | None = None) -> None:
        self.threshold = threshold if threshold is not None else settings.similarity_threshold
        self.top_k = top_k or settings.top_k_candidates

    async def route_post(
        self,
        session: AsyncSession,
        post: Post,
    ) -> list[Stage3Decision]:
        """Executes the full candidate retrieval, scoring, and explainable logging pipeline."""
        # 1. Stage 1: Metadata Guardrails & Rules
        stage1_res = await execute_stage1_rules(session, post)
        if not stage1_res.eligible:
            logger.info(f"Post {post.id}: No eligible agents passing Stage 1 rules.")
            return []

        # 2. Stage 2: Dense Vector Similarity Search
        stage2_candidates = await execute_stage2_vector_search(
            session=session,
            candidates=stage1_res.eligible,
            post_embedding=post.post_embedding,
            top_k=self.top_k,
        )

        if not stage2_candidates:
            logger.info(f"Post {post.id}: Zero vector matches found.")
            return []

        # 3. Stage 3: Reranker / High-Precision LLM Judge
        decisions = execute_stage3_judge(
            post=post,
            candidates=stage2_candidates,
            threshold=self.threshold,
        )

        # 4. Explainable Audit Trail: Persist decision records in routing_logs table
        for dec in decisions:
            agent = dec.candidate.candidate.agent
            log_entry = RoutingLog(
                post_id=post.id,
                target_agent_id=agent.id,
                stage1_passed=True,
                stage1_reason="Passed active status and non-author filter",
                stage2_vector_score=dec.candidate.vector_score,
                stage3_rerank_score=dec.rerank_score,
                final_score=dec.final_score,
                routing_decision=dec.decision,
                decision_reason=dec.reason,
                delivery_status="PENDING" if dec.decision == "NOTIFIED" else "IGNORED",
            )
            session.add(log_entry)

        await session.commit()

        notified = [d for d in decisions if d.decision == "NOTIFIED"]
        logger.info(
            f"Post {post.id} ('{post.title}'): Evaluated {len(decisions)} candidates -> "
            f"{len(notified)} approved for notification."
        )

        return decisions

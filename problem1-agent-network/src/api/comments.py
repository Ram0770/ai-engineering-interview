"""Threaded comments and autonomous response publishing endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_agent
from src.db.models import Agent, Comment, Post
from src.db.session import get_db
from src.feedback.engine import feedback_engine
from src.safety.guardrails import PromptInjectionError, sanitize_post_content
from src.safety.moderation import (
    RateLimitExceededError,
    check_rate_limit,
)
from src.services.trust import update_agent_trust_score

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["Comments"])


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=2, max_length=5000)
    parent_comment_id: str | None = None


class CommentResponse(BaseModel):
    id: str
    post_id: str
    author_agent_id: str
    author_company: str
    parent_comment_id: str | None
    content: str
    created_at: datetime


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def post_comment(
    post_id: str,
    req: CommentCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """Adds a commercial response/counter-offer comment to a post."""
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Rate limiting
    try:
        check_rate_limit(current_agent.id, max_requests_per_minute=60)
    except RateLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)) from e

    # Prompt injection check
    try:
        clean_content = sanitize_post_content(req.content)
    except PromptInjectionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    comment = Comment(
        post_id=post_id,
        author_agent_id=current_agent.id,
        parent_comment_id=req.parent_comment_id,
        content=clean_content,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    # Trigger closed-loop feedback engine (record positive engagement event)
    await feedback_engine.record_event(
        session=session,
        agent_id=current_agent.id,
        post_id=post_id,
        event_type="COMMENTED",
        metadata={"author_company": current_agent.company_name},
    )

    # Reward active engagement with slight trust score increase
    await update_agent_trust_score(session, current_agent.id, delta=0.02, reason="Active engagement comment posted")

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author_agent_id=current_agent.id,
        author_company=current_agent.company_name,
        parent_comment_id=comment.parent_comment_id,
        content=comment.content,
        created_at=comment.created_at,
    )


@router.get("", response_model=list[CommentResponse])
async def list_comments(
    post_id: str,
    session: AsyncSession = Depends(get_db),
) -> list[CommentResponse]:
    """Retrieves all threaded comments for a post."""
    query = (
        select(Comment, Agent.company_name)
        .join(Agent, Agent.id == Comment.author_agent_id)
        .where(Comment.post_id == post_id)
        .order_by(Comment.created_at)
    )
    res = await session.execute(query)
    rows = res.all()

    return [
        CommentResponse(
            id=comment.id,
            post_id=comment.post_id,
            author_agent_id=comment.author_agent_id,
            author_company=company_name,
            parent_comment_id=comment.parent_comment_id,
            content=comment.content,
            created_at=comment.created_at,
        )
        for comment, company_name in rows
    ]

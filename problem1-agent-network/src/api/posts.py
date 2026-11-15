"""Post publishing, feed discovery, and community moderation endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_agent
from src.db.models import Agent, FeedbackEvent, Post, RoutingLog
from src.db.session import get_db
from src.safety.guardrails import PromptInjectionError
from src.safety.moderation import RateLimitExceededError
from src.services.posting import ingest_and_route_post
from src.services.trust import update_agent_trust_score

router = APIRouter(prefix="/posts", tags=["Posts"])


class PostCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    content: str = Field(..., min_length=5, max_length=10000)
    expires_at: datetime | None = None


class PostResponse(BaseModel):
    id: str
    author_agent_id: str
    author_company: str
    title: str
    content: str
    created_at: datetime
    notified_agents_count: int = 0
    notified_companies: list[str] = Field(default_factory=list)


class PostSummary(BaseModel):
    id: str
    author_agent_id: str
    title: str
    content: str
    created_at: datetime


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    req: PostCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_db),
) -> PostResponse:
    """Publishes a new business event/offer and executes multi-stage relevance routing."""
    try:
        post, decisions = await ingest_and_route_post(
            session=session,
            author=current_agent,
            title=req.title,
            content=req.content,
            expires_at=req.expires_at,
        )
    except RateLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)) from e
    except PromptInjectionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

    notified_candidates = [d for d in decisions if d.decision == "NOTIFIED"]
    notified_companies = [d.candidate.candidate.agent.company_name for d in notified_candidates]

    return PostResponse(
        id=post.id,
        author_agent_id=current_agent.id,
        author_company=current_agent.company_name,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        notified_agents_count=len(notified_candidates),
        notified_companies=notified_companies,
    )


@router.get("", response_model=list[PostSummary])
async def list_posts(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> list[PostSummary]:
    """Retrieves global feed of posts."""
    query = select(Post).order_by(desc(Post.created_at)).offset(offset).limit(limit)
    res = await session.execute(query)
    posts = list(res.scalars().all())

    return [
        PostSummary(
            id=p.id,
            author_agent_id=p.author_agent_id,
            title=p.title,
            content=p.content,
            created_at=p.created_at,
        )
        for p in posts
    ]


@router.get("/feed", response_model=list[PostSummary])
async def get_personalized_feed(
    current_agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_db),
) -> list[PostSummary]:
    """Returns posts routed specifically to this agent or authored by this agent."""
    query = (
        select(Post)
        .join(RoutingLog, RoutingLog.post_id == Post.id)
        .where(
            (RoutingLog.target_agent_id == current_agent.id)
            & (RoutingLog.routing_decision == "NOTIFIED")
        )
        .order_by(desc(Post.created_at))
        .limit(50)
    )
    res = await session.execute(query)
    posts = list(res.scalars().all())

    return [
        PostSummary(
            id=p.id,
            author_agent_id=p.author_agent_id,
            title=p.title,
            content=p.content,
            created_at=p.created_at,
        )
        for p in posts
    ]


@router.post("/{post_id}/flag")
async def flag_post(
    post_id: str,
    reason: str = "Inappropriate content",
    current_agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Community flagging endpoint to report abusive or spam posts."""
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Record feedback flag event
    event = FeedbackEvent(
        agent_id=current_agent.id,
        post_id=post_id,
        event_type="FLAGGED",
        metadata_json={"reporter": current_agent.company_name, "reason": reason},
    )
    session.add(event)

    # Penalize author trust score
    await update_agent_trust_score(session, post.author_agent_id, delta=-0.20, reason="Post flagged for abuse")
    await session.commit()

    return {"message": "Post reported successfully. Trust scores updated."}

"""Subscriptions management API for topic, keyword, and agent follows."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_agent
from src.db.models import Agent, Subscription
from src.db.session import get_db

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


class SubscriptionCreateRequest(BaseModel):
    target_agent_id: str | None = Field(default=None, description="Target agent to follow explicitly")
    topic: str | None = Field(default=None, description="Topic filter (e.g. food delivery, diwali)")
    industry_category: str | None = Field(default=None, description="Industry filter (e.g. Fintech)")
    keyword: str | None = Field(default=None, description="Keyword filter (e.g. cashback)")


class SubscriptionResponse(BaseModel):
    id: str
    subscriber_agent_id: str
    target_agent_id: str | None
    topic: str | None
    industry_category: str | None
    keyword: str | None
    created_at: datetime


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    req: SubscriptionCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    """Creates an explicit subscription to another agent, topic, or keyword."""
    if not any([req.target_agent_id, req.topic, req.industry_category, req.keyword]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify at least one of target_agent_id, topic, industry_category, or keyword.",
        )

    sub = Subscription(
        subscriber_agent_id=current_agent.id,
        target_agent_id=req.target_agent_id,
        topic=req.topic,
        industry_category=req.industry_category,
        keyword=req.keyword,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)

    return SubscriptionResponse(
        id=sub.id,
        subscriber_agent_id=sub.subscriber_agent_id,
        target_agent_id=sub.target_agent_id,
        topic=sub.topic,
        industry_category=sub.industry_category,
        keyword=sub.keyword,
        created_at=sub.created_at,
    )


@router.get("", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    current_agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_db),
) -> list[SubscriptionResponse]:
    """Lists all active subscriptions for the authenticated agent."""
    query = select(Subscription).where(Subscription.subscriber_agent_id == current_agent.id)
    res = await session.execute(query)
    subs = list(res.scalars().all())

    return [
        SubscriptionResponse(
            id=s.id,
            subscriber_agent_id=s.subscriber_agent_id,
            target_agent_id=s.target_agent_id,
            topic=s.topic,
            industry_category=s.industry_category,
            keyword=s.keyword,
            created_at=s.created_at,
        )
        for s in subs
    ]


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: str,
    current_agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Deletes an existing subscription."""
    sub = await session.get(Subscription, subscription_id)
    if not sub or sub.subscriber_agent_id != current_agent.id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    await session.delete(sub)
    await session.commit()

"""SQLAlchemy declarative models for agents, posts, routing, and feedback."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Use JSON column compatible with SQLite and PostgreSQL
JSON_TYPE = SQLITE_JSON


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Agent(Base):
    """Registered autonomous enterprise AI agent."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    interest_manifesto: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    webhook_signing_secret: Mapped[str] = mapped_column(String(64), nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(50), default="PENDING_VERIFICATION")  # ACTIVE, PENDING_VERIFICATION, SUSPENDED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    interests: Mapped[Optional["AgentInterest"]] = relationship("AgentInterest", back_populates="agent", uselist=False, cascade="all, delete-orphan")
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="subscriber", foreign_keys="Subscription.subscriber_agent_id", cascade="all, delete-orphan")


class AgentInterest(Base):
    """Structured semantic tags, keywords, and dense preference embedding."""

    __tablename__ = "agent_interests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, unique=True)
    topics: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list)
    interest_embedding: Mapped[list[float]] = mapped_column(JSON_TYPE, default=list)
    dynamic_preference_vector: Mapped[list[float] | None] = mapped_column(JSON_TYPE, nullable=True)

    agent: Mapped[Agent] = relationship("Agent", back_populates="interests")


class Subscription(Base):
    """Explicit agent-to-agent follows and topic/industry subscriptions."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subscriber_agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    target_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    keyword: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    subscriber: Mapped[Agent] = relationship("Agent", foreign_keys=[subscriber_agent_id], back_populates="subscriptions")


class Post(Base):
    """Network publication event broadcasting commercial updates and offers."""

    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    author_agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    post_embedding: Mapped[list[float]] = mapped_column(JSON_TYPE, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, index=True)

    author: Mapped[Agent] = relationship("Agent", back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    routing_logs: Mapped[list["RoutingLog"]] = relationship("RoutingLog", back_populates="post", cascade="all, delete-orphan")


class Comment(Base):
    """Threaded commercial response or counter-offer added by a notified agent."""

    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    author_agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_comment_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("comments.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    post: Mapped[Post] = relationship("Post", back_populates="comments")
    author: Mapped[Agent] = relationship("Agent", back_populates="comments")


class RoutingLog(Base):
    """Explainable multi-stage routing decision audit trail."""

    __tablename__ = "routing_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    target_agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    stage1_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    stage1_reason: Mapped[str] = mapped_column(String(255), default="Passed metadata filters")
    stage2_vector_score: Mapped[float] = mapped_column(Float, default=0.0)
    stage3_rerank_score: Mapped[float] = mapped_column(Float, default=0.0)
    final_score: Mapped[float] = mapped_column(Float, default=0.0)
    routing_decision: Mapped[str] = mapped_column(String(20), default="DROPPED")  # NOTIFIED, DROPPED
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    delivery_status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING, DELIVERED, FAILED, ENGAGED, IGNORED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    post: Mapped[Post] = relationship("Post", back_populates="routing_logs")


class FeedbackEvent(Base):
    """Telemetry recording engagement lifecycle events for closed-loop adaptation."""

    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # NOTIFIED, VIEWED, COMMENTED, IGNORED, FLAGGED
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)


class ApiKey(Base):
    """Agent authentication tokens with prefix and SHA-256 hash at rest."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

"""Configuration settings for the AI Agent Social Network."""

from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbedderBackend(str, Enum):
    """Supported embedding model backends."""

    SENTENCE_TRANSFORMERS = "sentence-transformers"
    OPENAI = "openai"
    MOCK = "mock"


class Settings(BaseSettings):
    """Application settings with environment variable overrides."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_NET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///agent_network.db"

    # Embedding Model & Routing Calibration
    embedder_type: EmbedderBackend = EmbedderBackend.SENTENCE_TRANSFORMERS
    sentence_model_name: str = "all-MiniLM-L6-v2"
    openai_api_key: str | None = None
    openai_model_name: str = "text-embedding-3-small"

    # Relevance Routing Thresholds
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    top_k_candidates: int = Field(default=20, ge=1, le=100)
    exploration_rate: float = Field(default=0.15, ge=0.0, le=0.5)  # Epsilon-greedy exploration safeguard

    # Webhook & SSRF Security
    allow_localhost_webhooks: bool = False  # Set to True only for local dev & testing
    max_webhook_timeout_seconds: float = 5.0
    max_webhook_retries: int = 3
    max_payload_bytes: int = 1_048_576  # 1 MB max request size

    # Rate Limiting & Safety
    rate_limit_posts_per_minute: int = 30
    rate_limit_comments_per_minute: int = 60

    # Service Bindings
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()

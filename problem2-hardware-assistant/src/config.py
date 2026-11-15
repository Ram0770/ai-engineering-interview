"""Configuration management for the Hardware Assistant."""

from enum import Enum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMBackend(str, Enum):
    """Supported LLM backends."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MOCK = "mock"


class Settings(BaseSettings):
    """Hardware assistant application settings."""

    model_config = SettingsConfigDict(
        env_prefix="HW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Settings
    backend: LLMBackend = LLMBackend.OLLAMA
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-haiku-20240307"

    # Execution limits & safety
    execution_timeout_seconds: float = Field(default=5.0, ge=0.5, le=30.0)
    max_output_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)  # 1 MB default
    allow_sudo: bool = True

    # Caching configuration
    static_cache_ttl_seconds: int = 3600  # 1 hour for static hardware specs
    dynamic_cache_ttl_seconds: int = 5  # 5 seconds for volatile metrics (e.g. free RAM, battery)

    # Audit logging
    audit_log_path: Path = Path("audit.log")

    @property
    def is_cloud_backend(self) -> bool:
        """Returns True if the configured backend transmits data outside localhost."""
        return self.backend in (LLMBackend.OPENAI, LLMBackend.ANTHROPIC)


settings = Settings()

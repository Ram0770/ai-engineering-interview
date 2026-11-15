"""LLM client protocol and chat communication models."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Structured tool call invocation emitted by an LLM."""

    id: str = Field(default="call_0")
    name: str = Field(..., description="Registered tool name to invoke")
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """Unified message structure across local and cloud LLM providers."""

    role: str = Field(..., description="'system', 'user', 'assistant', or 'tool'")
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatResponse(BaseModel):
    """Model response payload containing text and/or tool invocations."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str = "stop"


class LLMClient(ABC):
    """Abstract interface decoupling the assistant from specific LLM vendors."""

    @abstractmethod
    def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        """Sends a conversation history and tool schemas to the model."""
        pass

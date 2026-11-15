"""Cloud LLM adapters for OpenAI and Anthropic Claude."""

import json
from typing import Any

import httpx

from src.config import settings
from src.llm.base import ChatMessage, ChatResponse, LLMClient, ToolCall


class OpenAIClient(LLMClient):
    """OpenAI API client adapter with function calling."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        if not self.api_key:
            raise ValueError("OpenAI API key is missing. Set HW_OPENAI_API_KEY or pass api_key.")

    def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        formatted_messages: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
            if msg.role == "tool":
                entry["tool_call_id"] = msg.tool_call_id or "call_0"
            elif msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            formatted_messages.append(entry)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
        }
        if tools:
            payload["tools"] = tools

        with httpx.Client(timeout=30.0) as client:
            res = client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()

        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content")

        tool_calls: list[ToolCall] = []
        raw_tc = msg.get("tool_calls", [])
        for item in raw_tc:
            fn = item["function"]
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=item["id"], name=fn["name"], arguments=args))

        return ChatResponse(content=content, tool_calls=tool_calls)


class AnthropicClient(LLMClient):
    """Anthropic Claude API client adapter with tool use."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.anthropic_model
        if not self.api_key:
            raise ValueError("Anthropic API key is missing. Set HW_ANTHROPIC_API_KEY or pass api_key.")

    def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        url = "https://api.anthropic.com/v1/messages"
        headers: dict[str, str] = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Format Anthropic tool schemas and messages
        system_prompt = ""
        anthropic_msgs: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content or ""
            elif msg.role in ("user", "assistant"):
                anthropic_msgs.append({"role": msg.role, "content": msg.content or ""})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_msgs,
            "max_tokens": 1024,
        }
        if system_prompt:
            payload["system"] = system_prompt

        with httpx.Client(timeout=30.0) as client:
            res = client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()

        content_parts = data.get("content", [])
        text_content = ""
        tool_calls: list[ToolCall] = []

        for part in content_parts:
            if part.get("type") == "text":
                text_content += part.get("text", "")
            elif part.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=part.get("id", "call_0"),
                        name=part.get("name", ""),
                        arguments=part.get("input", {}),
                    )
                )

        return ChatResponse(content=text_content, tool_calls=tool_calls)

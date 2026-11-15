"""Ollama local LLM client ensuring 100% on-device private inference."""

import json
from typing import Any

import httpx

from src.config import settings
from src.llm.base import ChatMessage, ChatResponse, LLMClient, ToolCall


class OllamaClient(LLMClient):
    """Local Ollama client using Ollama's /api/chat endpoint with native tool calling."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout

    def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        url = f"{self.base_url}/api/chat"

        # Format messages for Ollama API
        formatted_messages: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            formatted_messages.append(entry)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": False,
        }

        if tools:
            payload["tools"] = tools

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()

            msg_data = data.get("message", {})
            content = msg_data.get("content")

            # Parse tool calls from Ollama response
            tool_calls: list[ToolCall] = []
            raw_tool_calls = msg_data.get("tool_calls", [])
            for idx, tc in enumerate(raw_tool_calls):
                func = tc.get("function", {})
                fn_name = func.get("name", "")
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                tool_calls.append(ToolCall(id=f"ollama_call_{idx}", name=fn_name, arguments=args))

            return ChatResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=data.get("done_reason", "stop"),
            )

        except httpx.ConnectError:
            err_msg = (
                f"Could not connect to Ollama at {self.base_url}. "
                "Ensure Ollama is running locally ('ollama serve') or run with '--backend mock' for offline tests."
            )
            return ChatResponse(content=err_msg, finish_reason="error")
        except Exception as e:
            return ChatResponse(
                content=f"Ollama request error: {str(e)}",
                finish_reason="error",
            )

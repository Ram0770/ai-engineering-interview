"""Session management, conversation history, and tiered cache with TTL."""

import time

from src.config import settings
from src.llm.base import ChatMessage, ToolCall
from src.models.hardware import ToolResult

STATIC_TOOLS = {
    "get_cpu_info",
    "get_memory_topology",
    "get_storage_devices",
    "get_gpu_info",
    "get_motherboard_bios_info",
    "get_os_kernel_info",
}

DYNAMIC_TOOLS = {
    "get_memory_summary",
    "get_battery_info",
}


class SessionManager:
    """Maintains multi-turn context and implements tiered TTL hardware caching."""

    def __init__(
        self,
        static_ttl: int | None = None,
        dynamic_ttl: int | None = None,
    ) -> None:
        self.static_ttl = static_ttl or settings.static_cache_ttl_seconds
        self.dynamic_ttl = dynamic_ttl or settings.dynamic_cache_ttl_seconds

        self.messages: list[ChatMessage] = []
        # Key: tool_name -> (ToolResult, timestamp)
        self._cache: dict[str, tuple[ToolResult, float]] = {}

    def add_message(
        self,
        role: str,
        content: str | None = None,
        tool_calls: list[ToolCall] | None = None,
        tool_call_id: str | None = None,
        name: str | None = None,
    ) -> ChatMessage:
        """Appends a new turn to the conversation history."""
        msg = ChatMessage(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            name=name,
        )
        self.messages.append(msg)
        return msg

    def get_cached_result(self, tool_name: str) -> ToolResult | None:
        """Retrieves a cached tool result if within its tiered TTL."""
        entry = self._cache.get(tool_name)
        if not entry:
            return None

        result, timestamp = entry
        age = time.time() - timestamp

        ttl = self.dynamic_ttl if tool_name in DYNAMIC_TOOLS else self.static_ttl
        if age < ttl:
            return result

        # Invalidate expired entry
        del self._cache[tool_name]
        return None

    def cache_result(self, tool_name: str, result: ToolResult) -> None:
        """Stores a successful tool execution in the tiered cache."""
        if result.exit_code == 0 and result.parsed is not None:
            self._cache[tool_name] = (result, time.time())

    def invalidate_cache(self, tool_name: str | None = None) -> None:
        """Clears all cached hardware entries or a specific tool."""
        if tool_name:
            self._cache.pop(tool_name, None)
        else:
            self._cache.clear()

    @property
    def cached_tools(self) -> list[str]:
        """List of currently valid cached tool names."""
        valid: list[str] = []
        for name in list(self._cache.keys()):
            if self.get_cached_result(name) is not None:
                valid.append(name)
        return valid

"""Session history and tiered cache TTL tests."""

import time

from src.models.hardware import MemorySummary, ToolResult
from src.session import SessionManager


def test_session_multi_turn_context() -> None:
    """Verifies that conversation history is preserved across turns."""
    sm = SessionManager()
    sm.add_message("user", "What processor do I have?")
    sm.add_message("assistant", "You have an Intel Core i7-12700H.")
    sm.add_message("user", "And what about the GPU?")

    assert len(sm.messages) == 3
    assert sm.messages[0].content == "What processor do I have?"
    assert sm.messages[2].content == "And what about the GPU?"


def test_tiered_cache_ttl_and_invalidation() -> None:
    """Verifies that static hardware specs have long TTL and dynamic metrics have short TTL."""
    sm = SessionManager(static_ttl=10, dynamic_ttl=1)

    # Static tool: get_cpu_info
    cpu_res = ToolResult(
        tool_name="get_cpu_info",
        command_executed="lscpu",
        exit_code=0,
        raw_stdout="Intel",
        parsed={"model_name": "Intel i7"},
        provenance_tag="tool:get_cpu_info",
    )
    sm.cache_result("get_cpu_info", cpu_res)

    # Dynamic tool: get_memory_summary
    mem_res = ToolResult(
        tool_name="get_memory_summary",
        command_executed="free -b",
        exit_code=0,
        raw_stdout="Mem: 16GB",
        parsed=MemorySummary(total_bytes=100, used_bytes=50, free_bytes=50, available_bytes=50),
        provenance_tag="tool:get_memory_summary",
    )
    sm.cache_result("get_memory_summary", mem_res)

    # Immediately after caching, both are hit
    assert sm.get_cached_result("get_cpu_info") is not None
    assert sm.get_cached_result("get_memory_summary") is not None

    # Wait for dynamic TTL to expire (1.1s)
    time.sleep(1.1)

    # Dynamic metric should be invalidated
    assert sm.get_cached_result("get_memory_summary") is None
    # Static metric must remain cached
    assert sm.get_cached_result("get_cpu_info") is not None

    # Explicit invalidation
    sm.invalidate_cache("get_cpu_info")
    assert sm.get_cached_result("get_cpu_info") is None

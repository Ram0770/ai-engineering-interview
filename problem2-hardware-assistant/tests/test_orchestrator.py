"""Tests for orchestrator keyword fallback and tool dispatching."""

from eval.eval_suite import FixtureMockEngine
from src.llm.mock_client import MockLLMClient
from src.orchestrator import HardwareOrchestrator
from src.tools.registry import ToolRegistry


def test_keyword_fallback_tool_routing(mock_engine: FixtureMockEngine, tool_registry: ToolRegistry) -> None:
    """Verifies that queries activate fallback tool routing when the LLM outputs no tool calls."""
    # Create an empty LLM client that returns no tool calls
    empty_llm = MockLLMClient()
    orch = HardwareOrchestrator(empty_llm, mock_engine, tool_registry)

    # Keyword fallback should recognize "nvme" -> "get_storage_devices"
    ans, tools = orch.handle_user_query("Is my primary disk NVMe?")
    assert any(t.tool_name == "get_storage_devices" for t in tools)
    assert "NVMe SSD" in ans

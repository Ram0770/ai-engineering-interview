"""End-to-end integration tests for canonical assignment examples and follow-ups."""

from eval.eval_suite import FixtureMockEngine
from src.llm.mock_client import MockLLMClient
from src.orchestrator import HardwareOrchestrator
from src.tools.registry import ToolRegistry


def test_canonical_ram_upgrade_example(mock_engine: FixtureMockEngine, tool_registry: ToolRegistry) -> None:
    """Verifies the exact assignment example: 'Can I add more RAM, and how much?'"""
    llm = MockLLMClient()
    orch = HardwareOrchestrator(llm, mock_engine, tool_registry)

    # 1. Primary RAM upgrade query
    ans_ram, tools_ram = orch.handle_user_query("Can I add more RAM, and how much?")

    assert len(tools_ram) == 1
    assert tools_ram[0].tool_name == "get_memory_topology"

    # Must contain exact facts from assignment:
    # "You have 16 GB in 1 of 2 slots. The board supports up to 64 GB, so you can add a stick of up to 32 GB."
    assert "16 GB" in ans_ram
    assert "1 of 2" in ans_ram
    assert "64 GB" in ans_ram
    assert "32 GB" in ans_ram
    assert "*(Source: tool:get_memory_topology" in ans_ram

    # 2. Follow-up query in the same multi-turn session
    ans_gpu, tools_gpu = orch.handle_user_query("and what about the GPU?")

    assert len(tools_gpu) == 1
    assert tools_gpu[0].tool_name == "get_gpu_info"
    assert "NVIDIA" in ans_gpu
    assert "RTX 3060" in ans_gpu
    assert "*(Source: tool:get_gpu_info" in ans_gpu

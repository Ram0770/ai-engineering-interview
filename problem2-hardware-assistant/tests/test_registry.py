"""Tests for tool registry and schema generation."""

from eval.eval_suite import FixtureMockEngine
from src.tools.registry import ToolRegistry


def test_dynamic_tool_registration(mock_engine: FixtureMockEngine) -> None:
    registry = ToolRegistry(mock_engine, include_all=True)
    names = registry.registered_tool_names

    assert "get_cpu_info" in names
    assert "get_memory_summary" in names
    assert "get_memory_topology" in names
    assert "get_storage_devices" in names
    assert "get_gpu_info" in names
    assert "get_battery_info" in names
    assert "get_os_kernel_info" in names
    assert "get_motherboard_bios_info" in names

    schemas = registry.get_openai_tool_definitions()
    assert len(schemas) == len(names)
    for s in schemas:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "description" in s["function"]

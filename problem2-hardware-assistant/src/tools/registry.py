"""Dynamic tool registry with capability-based filtering."""

from typing import Any

from src.execution.engine import SafeExecutionEngine
from src.tools.base import BaseHardwareTool
from src.tools.battery import BatteryTool
from src.tools.cpu import CPUTool
from src.tools.gpu import GPUTool
from src.tools.memory import MemorySummaryTool, MemoryTopologyTool
from src.tools.motherboard import MotherboardTool
from src.tools.os_kernel import OSKernelTool
from src.tools.storage import StorageTool


class ToolRegistry:
    """Manages available hardware tools and produces tool definitions for LLMs."""

    def __init__(self, engine: SafeExecutionEngine, include_all: bool = False) -> None:
        self.engine = engine
        self._tools: dict[str, BaseHardwareTool] = {}
        self._all_tools: list[BaseHardwareTool] = [
            CPUTool(),
            MemorySummaryTool(),
            MemoryTopologyTool(),
            StorageTool(),
            GPUTool(),
            BatteryTool(),
            OSKernelTool(),
            MotherboardTool(),
        ]
        self._register_available(include_all=include_all)

    def _register_available(self, include_all: bool = False) -> None:
        """Populates registry with tools that can run or all tools if forced."""
        for tool in self._all_tools:
            if include_all or tool.is_available(self.engine):
                self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseHardwareTool | None:
        """Retrieves a registered tool by its identifier."""
        return self._tools.get(name)

    @property
    def registered_tool_names(self) -> list[str]:
        """List of active tool names."""
        return sorted(self._tools.keys())

    def get_openai_tool_definitions(self) -> list[dict[str, Any]]:
        """Returns JSON schema definitions for all registered tools."""
        return [tool.get_openai_tool_definition() for tool in self._tools.values()]

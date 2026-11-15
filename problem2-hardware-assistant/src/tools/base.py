"""Base classes and schemas for hardware inspection tools."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from src.execution.engine import SafeExecutionEngine
from src.models.hardware import ToolResult


class EmptyParameters(BaseModel):
    """Parameter schema for tools requiring no input arguments."""

    pass


class BaseHardwareTool(ABC):
    """Abstract base class for all sandboxed hardware inspection tools."""

    name: str
    description: str
    parameters_schema: type[BaseModel] = EmptyParameters
    is_privileged: bool = False
    requires_root_without_fallback: bool = False

    @abstractmethod
    def is_available(self, engine: SafeExecutionEngine) -> bool:
        """Determines if the tool can execute in the current host environment."""
        pass

    @abstractmethod
    def run(self, engine: SafeExecutionEngine, **kwargs: Any) -> ToolResult:
        """Executes the tool using the safe execution engine and returns a structured ToolResult."""
        pass

    def get_openai_tool_definition(self) -> dict[str, Any]:
        """Generates OpenAI / Ollama standard tool calling specification."""
        schema = self.parameters_schema.model_json_schema()
        # Clean up JSON schema for LLM function calling
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

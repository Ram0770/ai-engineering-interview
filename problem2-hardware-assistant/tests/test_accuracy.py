"""Anti-hallucination, numeric verification, and fact provenance tests."""

from eval.eval_suite import FixtureMockEngine
from src.llm.mock_client import MockLLMClient
from src.models.hardware import ToolResult
from src.orchestrator import HardwareOrchestrator
from src.tools.registry import ToolRegistry


def test_anti_hallucination_guard(mock_engine: FixtureMockEngine, tool_registry: ToolRegistry) -> None:
    """Verifies that the orchestrator reports missing data instead of hallucinating specs."""
    llm = MockLLMClient()
    orch = HardwareOrchestrator(llm, mock_engine, tool_registry)

    # Ask an unanswerable question with no hardware tool available
    ans, tools = orch.handle_user_query("What is the temperature of the water cooling loop in Celsius?")
    assert "I cannot determine this from system data" in ans


def test_numeric_claim_verification(mock_engine: FixtureMockEngine, tool_registry: ToolRegistry) -> None:
    """Verifies that invented numbers in LLM output trigger a warning notice."""
    llm = MockLLMClient()
    orch = HardwareOrchestrator(llm, mock_engine, tool_registry)

    fake_result = ToolResult(
        tool_name="get_memory_topology",
        command_executed="dmidecode -t memory",
        exit_code=0,
        raw_stdout="",
        parsed={
            "installed_capacity_bytes": 17179869184,  # 16 GB
            "max_capacity_bytes": 68719476736,       # 64 GB
            "total_slots": 2,
            "used_slots": 1,
        },
        provenance_tag="tool:get_memory_topology",
    )

    # Valid answer with numbers 16, 64, 2, 1
    valid_ans = "You have 16 GB in 1 of 2 slots. Maximum is 64 GB."
    checked_valid = orch._verify_numeric_claims(valid_ans, [fake_result])
    assert "*[Notice: Numeric claim(s)" not in checked_valid

    # Hallucinated answer with invented number 999
    hallucinated_ans = "You have 16 GB in 1 of 2 slots with 999 gigahertz speed."
    checked_bad = orch._verify_numeric_claims(hallucinated_ans, [fake_result])
    assert "*[Notice: Numeric claim(s) 999 could not be directly verified against raw system JSON.]*" in checked_bad


def test_provenance_attribution(mock_engine: FixtureMockEngine, tool_registry: ToolRegistry) -> None:
    """Verifies that each answer cites the originating tool and command in its provenance tag."""
    llm = MockLLMClient()
    orch = HardwareOrchestrator(llm, mock_engine, tool_registry)
    ans, tools = orch.handle_user_query("Can I add more RAM, and how much?")

    assert "*(Source: tool:get_memory_topology" in ans

"""Evaluation benchmark runner for the Linux Hardware Q&A Assistant."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure problem2-hardware-assistant root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.discovery import SystemCapabilities
from src.execution.engine import SafeExecutionEngine
from src.llm.base import LLMClient
from src.llm.mock_client import MockLLMClient
from src.llm.ollama_client import OllamaClient
from src.orchestrator import HardwareOrchestrator
from src.tools.registry import ToolRegistry


class FixtureCapabilities(SystemCapabilities):
    """Capabilities simulating a full Linux environment with discovered binaries."""

    def __init__(self) -> None:
        super().__init__()
        self.os_type = "Linux"
        self.is_linux = True
        self.is_windows = False
        self.procfs_available = True
        self.sysfs_available = True
        self.has_sudo_nopasswd_dmidecode = True
        self.is_virtual_machine = False

    def is_available(self, tool_name: str) -> bool:
        return True

    def get_binary_path(self, tool_name: str) -> str | None:
        return f"/usr/bin/{tool_name}"


class FixtureMockEngine(SafeExecutionEngine):
    """Execution engine serving deterministic multi-distro fixture data."""

    def __init__(self, fixtures_dir: Path) -> None:
        super().__init__(capabilities=FixtureCapabilities())
        self.fixtures_dir = fixtures_dir

    def execute_command(self, binary_name: str, args: list[str], use_sudo: bool = False, caller: str = "eval") -> Any:
        from src.execution.engine import (
            DMIDECODE_ALLOWED_TYPE_ARGS,
            ExecutionResult,
            SecurityViolationError,
        )

        self.validate_argument(binary_name)
        for arg in args:
            self.validate_argument(arg)

        if use_sudo and binary_name == "dmidecode":
            if len(args) != 2 or args[0] != "-t" or args[1] not in DMIDECODE_ALLOWED_TYPE_ARGS:
                raise SecurityViolationError(f"Unpermitted dmidecode arguments: {args!r}")

        if binary_name == "lscpu":
            txt = (self.fixtures_dir / "lscpu.txt").read_text(encoding="utf-8")
            return ExecutionResult(argv=["lscpu"], exit_code=0, stdout=txt, stderr="", duration_ms=1.0)
        elif binary_name == "free":
            txt = (self.fixtures_dir / "free_b.txt").read_text(encoding="utf-8")
            return ExecutionResult(argv=["free", "-b"], exit_code=0, stdout=txt, stderr="", duration_ms=1.0)
        elif binary_name == "dmidecode":
            txt = (self.fixtures_dir / "dmidecode_memory.txt").read_text(encoding="utf-8")
            return ExecutionResult(argv=["dmidecode"] + args, exit_code=0, stdout=txt, stderr="", duration_ms=1.0)
        elif binary_name == "lsblk":
            txt = (self.fixtures_dir / "lsblk_json.json").read_text(encoding="utf-8")
            return ExecutionResult(argv=["lsblk"], exit_code=0, stdout=txt, stderr="", duration_ms=1.0)
        elif binary_name == "lspci":
            txt = (self.fixtures_dir / "lspci_vmm.txt").read_text(encoding="utf-8")
            return ExecutionResult(argv=["lspci", "-vmm"], exit_code=0, stdout=txt, stderr="", duration_ms=1.0)
        elif binary_name == "uname":
            return ExecutionResult(argv=["uname", "-r"], exit_code=0, stdout="5.15.0-105-generic\n", stderr="", duration_ms=0.5)

        return super().execute_command(binary_name, args, use_sudo=use_sudo, caller=caller)

    def read_virtual_file(self, file_path: Path, max_bytes: int | None = None, caller: str = "eval") -> str:
        p = str(file_path).replace("\\", "/")
        if "os-release" in p:
            return 'NAME="Ubuntu"\nVERSION="22.04 LTS"\n'
        elif "uptime" in p:
            return "86400.00 172800.00\n"
        elif "power_supply" in p:
            if "status" in p:
                return "Discharging\n"
            elif "capacity" in p:
                return "85\n"
            elif "energy_full" in p:
                return "50000000\n"
            elif "energy_full_design" in p:
                return "52000000\n"
        elif "dmi/id" in p:
            if "board_vendor" in p:
                return "Lenovo\n"
            elif "board_name" in p:
                return "21AH001HUS\n"
            elif "bios_vendor" in p:
                return "LENOVO\n"
            elif "bios_version" in p:
                return "N3BET56W (1.34 )\n"
            elif "bios_date" in p:
                return "10/12/2023\n"
        return ""


def run_eval(backend: str = "mock", model_name: str = "llama3.2:3b") -> dict[str, Any]:
    base_dir = Path(__file__).resolve().parent
    cases_file = base_dir / "eval_cases.json"
    fixtures_dir = base_dir.parent / "tests" / "fixtures" / "synthetic" / "ubuntu_2204"

    cases: list[dict[str, Any]] = json.loads(cases_file.read_text(encoding="utf-8"))

    # Setup LLM client
    llm: LLMClient
    if backend == "ollama":
        print(f"Connecting to live local Ollama model '{model_name}'...")
        llm = OllamaClient(model=model_name)
    else:
        llm = MockLLMClient()

    engine = FixtureMockEngine(fixtures_dir)
    registry = ToolRegistry(engine, include_all=True)

    passed_count = 0
    total_count = len(cases)
    results: list[dict[str, Any]] = []

    print("\n=======================================================")
    print(f"Running Hardware Q&A Assistant Evaluation ({total_count} cases)")
    print(f"Backend: {backend} | Model: {model_name if backend == 'ollama' else 'Mock'}")
    print("=======================================================\n")

    for case in cases:
        cid = case["id"]
        q = case["question"]
        expected_tools = case["expected_tools"]
        required_facts = case.get("required_facts", [])

        # Fresh orchestrator per case to evaluate clean retrieval
        orchestrator = HardwareOrchestrator(
            llm_client=llm,
            execution_engine=engine,
            tool_registry=registry,
        )

        answer, executed_tools = orchestrator.handle_user_query(q)
        executed_names = [t.tool_name for t in executed_tools]

        # Verification rules:
        # 1. Did it invoke at least one of the expected tools?
        tool_ok = any(t in executed_names for t in expected_tools)

        # 2. Are required facts present in the answer text?
        facts_ok = True
        missing_facts = []
        for fact in required_facts:
            if fact.lower() not in answer.lower():
                facts_ok = False
                missing_facts.append(fact)

        case_passed = tool_ok and facts_ok
        if case_passed:
            passed_count += 1
            status_str = "[PASS]"
        else:
            status_str = "[FAIL]"

        print(f"{status_str} {cid}: \"{q}\"")
        if not tool_ok:
            print(f"   -> Tool mismatch: executed {executed_names}, expected one of {expected_tools}")
        if not facts_ok:
            print(f"   -> Missing facts in answer: {missing_facts}")

        results.append({
            "id": cid,
            "question": q,
            "passed": case_passed,
            "executed_tools": executed_names,
            "expected_tools": expected_tools,
            "missing_facts": missing_facts,
            "answer_snippet": answer[:150],
        })

    pass_rate = (passed_count / total_count) * 100.0
    print("\n-------------------------------------------------------")
    print(f"Evaluation Summary: {passed_count}/{total_count} passed ({pass_rate:.1f}%)")
    print("-------------------------------------------------------\n")

    return {
        "total": total_count,
        "passed": passed_count,
        "pass_rate_percent": pass_rate,
        "backend": backend,
        "model": model_name,
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Hardware Q&A Assistant")
    parser.add_argument("--backend", default="mock", choices=["mock", "ollama"])
    parser.add_argument("--model", default="llama3.2:3b")
    args = parser.parse_args()

    summary = run_eval(backend=args.backend, model_name=args.model)
    if summary["passed"] != summary["total"]:
        sys.exit(1)

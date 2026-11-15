"""CPU inspection tool supporting lscpu and /proc/cpuinfo fallback."""

from pathlib import Path
from typing import Any

from src.execution.engine import SafeExecutionEngine
from src.models.hardware import CPUInfo, ToolResult
from src.tools.base import BaseHardwareTool, EmptyParameters


class CPUTool(BaseHardwareTool):
    """Inspects processor model, cores, frequency, and architecture."""

    name = "get_cpu_info"
    description = (
        "Retrieves central processor (CPU) information including model name, "
        "architecture, physical sockets, core counts, logical threads, and frequency."
    )
    parameters_schema = EmptyParameters

    def is_available(self, engine: SafeExecutionEngine) -> bool:
        return (
            engine.capabilities.is_available("lscpu")
            or Path("/proc/cpuinfo").exists()
        )

    def run(self, engine: SafeExecutionEngine, **kwargs: Any) -> ToolResult:
        if engine.capabilities.is_available("lscpu"):
            res = engine.execute_command("lscpu", [])
            if res.exit_code == 0:
                parsed = self.parse_lscpu(res.stdout)
                return ToolResult(
                    tool_name=self.name,
                    command_executed="lscpu",
                    exit_code=res.exit_code,
                    raw_stdout=res.stdout,
                    parsed=parsed,
                    duration_ms=res.duration_ms,
                    provenance_tag="tool:get_cpu_info (lscpu)",
                )

        # Fallback to /proc/cpuinfo
        cpuinfo_path = Path("/proc/cpuinfo")
        if cpuinfo_path.exists():
            try:
                content = engine.read_virtual_file(cpuinfo_path)
                parsed = self.parse_proc_cpuinfo(content)
                return ToolResult(
                    tool_name=self.name,
                    command_executed="read /proc/cpuinfo",
                    exit_code=0,
                    raw_stdout=content,
                    parsed=parsed,
                    duration_ms=0.5,
                    provenance_tag="tool:get_cpu_info (/proc/cpuinfo)",
                )
            except Exception as e:
                return ToolResult(
                    tool_name=self.name,
                    command_executed="read /proc/cpuinfo",
                    exit_code=-1,
                    raw_stdout="",
                    error=f"Failed to read /proc/cpuinfo: {e}",
                    provenance_tag="tool:get_cpu_info",
                )

        return ToolResult(
            tool_name=self.name,
            command_executed="lscpu",
            exit_code=127,
            raw_stdout="",
            error="Neither 'lscpu' nor '/proc/cpuinfo' is available.",
            provenance_tag="tool:get_cpu_info",
        )

    def parse_lscpu(self, stdout: str) -> CPUInfo:
        """Parses standard key-value output from lscpu."""
        data: dict[str, str] = {}
        flags: list[str] = []

        for line in stdout.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip().lower()] = v.strip()

        model_name = (
            data.get("model name")
            or data.get("model name(s)")
            or data.get("cpu(s)")
            or "Unknown CPU"
        )
        architecture = data.get("architecture", "Unknown")
        sockets = int(data.get("socket(s)", 1))
        cores_per_socket = int(data.get("core(s) per socket", 1))
        threads_per_core = int(data.get("thread(s) per core", 1))
        total_cores = int(data.get("cpu(s)", sockets * cores_per_socket * threads_per_core))

        min_mhz: float | None = None
        max_mhz: float | None = None
        if "cpu min mhz" in data:
            try:
                min_mhz = float(data["cpu min mhz"].replace(",", "."))
            except ValueError:
                pass
        if "cpu max mhz" in data:
            try:
                max_mhz = float(data["cpu max mhz"].replace(",", "."))
            except ValueError:
                pass

        if "flags" in data:
            raw_flags = data["flags"].split()
            virt_candidates = {"vmx", "svm", "hypervisor"}
            flags = [f for f in raw_flags if f in virt_candidates]

        return CPUInfo(
            model_name=model_name,
            architecture=architecture,
            sockets=sockets,
            cores_per_socket=cores_per_socket,
            threads_per_core=threads_per_core,
            total_logical_cores=total_cores,
            min_mhz=min_mhz,
            max_mhz=max_mhz,
            virtualization_flags=flags,
        )

    def parse_proc_cpuinfo(self, content: str) -> CPUInfo:
        """Parses raw /proc/cpuinfo Linux virtual file."""
        model_name = "Unknown CPU"
        flags: list[str] = []
        logical_count = 0
        cores_per_socket = 1
        mhz: float | None = None

        for line in content.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if ":" in line_str:
                k, v = [x.strip() for x in line_str.split(":", 1)]
                k_lower = k.lower()
                if k_lower == "processor":
                    logical_count += 1
                elif k_lower == "model name" and model_name == "Unknown CPU":
                    model_name = v
                elif k_lower == "cpu cores":
                    try:
                        cores_per_socket = int(v)
                    except ValueError:
                        pass
                elif k_lower == "cpu mhz" and mhz is None:
                    try:
                        mhz = float(v)
                    except ValueError:
                        pass
                elif k_lower == "flags" and not flags:
                    virt_candidates = {"vmx", "svm", "hypervisor"}
                    flags = [f for f in v.split() if f in virt_candidates]

        logical_count = max(1, logical_count)
        return CPUInfo(
            model_name=model_name,
            architecture="x86_64" if "vmx" in flags or "svm" in flags else "Unknown",
            sockets=1,
            cores_per_socket=cores_per_socket,
            threads_per_core=max(1, logical_count // cores_per_socket),
            total_logical_cores=logical_count,
            min_mhz=mhz,
            max_mhz=mhz,
            virtualization_flags=flags,
        )

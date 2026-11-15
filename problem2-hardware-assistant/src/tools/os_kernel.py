"""Operating system and Linux kernel information tool."""

import platform
from pathlib import Path
from typing import Any

from src.execution.engine import SafeExecutionEngine
from src.models.hardware import OSKernelInfo, ToolResult
from src.tools.base import BaseHardwareTool, EmptyParameters


class OSKernelTool(BaseHardwareTool):
    """Inspects operating system release, Linux kernel version, architecture, and uptime."""

    name = "get_os_kernel_info"
    description = (
        "Retrieves operating system distribution, kernel version release, system architecture, "
        "hostname, and host uptime."
    )
    parameters_schema = EmptyParameters

    def is_available(self, engine: SafeExecutionEngine) -> bool:
        return (
            engine.capabilities.is_available("uname")
            or Path("/etc/os-release").exists()
            or Path("/proc/uptime").exists()
        )

    def run(self, engine: SafeExecutionEngine, **kwargs: Any) -> ToolResult:
        os_name = "Linux"
        os_version = ""
        kernel_release = platform.release() or "Unknown"
        arch = platform.machine() or "x86_64"
        hostname = platform.node() or "localhost"
        uptime_seconds = 0.0

        # Read /etc/os-release
        os_release_path = Path("/etc/os-release")
        if os_release_path.exists():
            try:
                content = engine.read_virtual_file(os_release_path)
                parsed_release = self.parse_os_release(content)
                os_name = parsed_release.get("NAME", os_name)
                os_version = parsed_release.get("VERSION", os_version)
            except Exception:
                pass

        # Query uname -r
        if engine.capabilities.is_available("uname"):
            res = engine.execute_command("uname", ["-r"])
            if res.exit_code == 0 and res.stdout.strip():
                kernel_release = res.stdout.strip()

        # Query /proc/uptime
        uptime_path = Path("/proc/uptime")
        if uptime_path.exists():
            try:
                up_content = engine.read_virtual_file(uptime_path)
                parts = up_content.strip().split()
                if parts:
                    uptime_seconds = float(parts[0])
            except Exception:
                pass

        info = OSKernelInfo(
            os_name=os_name,
            os_version=os_version,
            kernel_release=kernel_release,
            kernel_architecture=arch,
            hostname=hostname,
            uptime_seconds=uptime_seconds,
        )

        return ToolResult(
            tool_name=self.name,
            command_executed="read /etc/os-release, uname -r, /proc/uptime",
            exit_code=0,
            raw_stdout=f"{os_name} {os_version} (Kernel {kernel_release})",
            parsed=info,
            duration_ms=0.5,
            provenance_tag="tool:get_os_kernel_info (/etc/os-release, uname)",
        )

    def parse_os_release(self, content: str) -> dict[str, str]:
        """Parses standard key-value shell format of /etc/os-release."""
        data: dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k_clean = k.strip()
                v_clean = v.strip().strip('"').strip("'")
                data[k_clean] = v_clean
        return data


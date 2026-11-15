"""Memory inspection tools for usage summary and physical DIMM topology."""

import re
from pathlib import Path
from typing import Any

from src.execution.engine import SafeExecutionEngine
from src.models.hardware import (
    MemorySlot,
    MemorySummary,
    MemoryTopology,
    ToolResult,
)
from src.tools.base import BaseHardwareTool, EmptyParameters


class MemorySummaryTool(BaseHardwareTool):
    """Inspects RAM and swap capacity, usage, and availability."""

    name = "get_memory_summary"
    description = (
        "Retrieves active system RAM and swap usage, total capacity, free memory, "
        "and available memory."
    )
    parameters_schema = EmptyParameters

    def is_available(self, engine: SafeExecutionEngine) -> bool:
        return engine.capabilities.is_available("free") or Path("/proc/meminfo").exists()

    def run(self, engine: SafeExecutionEngine, **kwargs: Any) -> ToolResult:
        if engine.capabilities.is_available("free"):
            res = engine.execute_command("free", ["-b"])
            if res.exit_code == 0:
                parsed = self.parse_free_b(res.stdout)
                return ToolResult(
                    tool_name=self.name,
                    command_executed="free -b",
                    exit_code=res.exit_code,
                    raw_stdout=res.stdout,
                    parsed=parsed,
                    duration_ms=res.duration_ms,
                    provenance_tag="tool:get_memory_summary (free -b)",
                )

        # Fallback to /proc/meminfo
        meminfo_path = Path("/proc/meminfo")
        if meminfo_path.exists():
            try:
                content = engine.read_virtual_file(meminfo_path)
                parsed = self.parse_proc_meminfo(content)
                return ToolResult(
                    tool_name=self.name,
                    command_executed="read /proc/meminfo",
                    exit_code=0,
                    raw_stdout=content,
                    parsed=parsed,
                    duration_ms=0.5,
                    provenance_tag="tool:get_memory_summary (/proc/meminfo)",
                )
            except Exception as e:
                return ToolResult(
                    tool_name=self.name,
                    command_executed="read /proc/meminfo",
                    exit_code=-1,
                    raw_stdout="",
                    error=f"Failed to read /proc/meminfo: {e}",
                    provenance_tag="tool:get_memory_summary",
                )

        return ToolResult(
            tool_name=self.name,
            command_executed="free -b",
            exit_code=127,
            raw_stdout="",
            error="Neither 'free' nor '/proc/meminfo' is available.",
            provenance_tag="tool:get_memory_summary",
        )

    def parse_free_b(self, stdout: str) -> MemorySummary:
        """Parses output from 'free -b'."""
        lines = [line.split() for line in stdout.strip().splitlines() if line.strip()]
        total = used = free = available = swap_total = swap_used = swap_free = 0

        for row in lines:
            if not row:
                continue
            header = row[0].rstrip(":").lower()
            if header in ("mem", "memory"):
                # Format: Mem: total used free shared buff/cache available
                total = int(row[1])
                used = int(row[2])
                free = int(row[3])
                available = int(row[6]) if len(row) >= 7 else free
            elif header == "swap":
                # Format: Swap: total used free
                swap_total = int(row[1])
                swap_used = int(row[2])
                swap_free = int(row[3])

        return MemorySummary(
            total_bytes=total,
            used_bytes=used,
            free_bytes=free,
            available_bytes=available,
            swap_total_bytes=swap_total,
            swap_used_bytes=swap_used,
            swap_free_bytes=swap_free,
        )

    def parse_proc_meminfo(self, content: str) -> MemorySummary:
        """Parses /proc/meminfo in KiB and converts to bytes."""
        metrics: dict[str, int] = {}
        for line in content.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k_clean = k.strip().lower()
                val_parts = v.strip().split()
                if val_parts and val_parts[0].isdigit():
                    metrics[k_clean] = int(val_parts[0]) * 1024  # kB to bytes

        total = metrics.get("memtotal", 0)
        free = metrics.get("memfree", 0)
        available = metrics.get("memavailable", free)
        used = max(0, total - available)
        swap_total = metrics.get("swaptotal", 0)
        swap_free = metrics.get("swapfree", 0)
        swap_used = max(0, swap_total - swap_free)

        return MemorySummary(
            total_bytes=total,
            used_bytes=used,
            free_bytes=free,
            available_bytes=available,
            swap_total_bytes=swap_total,
            swap_used_bytes=swap_used,
            swap_free_bytes=swap_free,
        )


class MemoryTopologyTool(BaseHardwareTool):
    """Inspects physical memory slots, DIMMs, upgrade capability, and max capacity."""

    name = "get_memory_topology"
    description = (
        "Retrieves physical RAM slot topology: total motherboard slots, empty slots, "
        "installed modules, form factor, speed, maximum supported motherboard capacity, "
        "and upgrade potential."
    )
    parameters_schema = EmptyParameters
    is_privileged = True

    def is_available(self, engine: SafeExecutionEngine) -> bool:
        # Available if dmidecode is discovered, or if procfs is available for fallback
        return engine.capabilities.is_available("dmidecode") or Path("/proc/meminfo").exists()

    def run(self, engine: SafeExecutionEngine, **kwargs: Any) -> ToolResult:
        # Check if dmidecode can be executed with sudo -n
        if engine.capabilities.is_available("dmidecode"):
            # Try execution with sudo -n
            res = engine.execute_command("dmidecode", ["-t", "memory"], use_sudo=True)
            if res.exit_code == 0 and res.stdout.strip():
                parsed = self.parse_dmidecode_memory(res.stdout, engine.capabilities.is_virtual_machine)
                return ToolResult(
                    tool_name=self.name,
                    command_executed="sudo -n dmidecode -t memory",
                    exit_code=res.exit_code,
                    raw_stdout=res.stdout,
                    parsed=parsed,
                    duration_ms=res.duration_ms,
                    provenance_tag="tool:get_memory_topology (dmidecode -t memory)",
                )

        # Unprivileged fallback: /proc/meminfo provides installed capacity, but slot topology cannot be queried
        meminfo_path = Path("/proc/meminfo")
        installed_bytes = 0
        if meminfo_path.exists():
            try:
                content = engine.read_virtual_file(meminfo_path)
                for line in content.splitlines():
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            installed_bytes = int(parts[1]) * 1024
            except Exception:
                pass

        diag = (
            "DMI physical slot topology and maximum capacity require elevated privileges. "
            "To enable deep topology inspection, install the scoped sudoers rule:\n"
            "  sudo cp sudoers.d/hw-assistant /etc/sudoers.d/hw-assistant\n"
            "Installed RAM was detected via unprivileged /proc/meminfo."
        )

        fallback_topology = MemoryTopology(
            total_slots=0,
            used_slots=1 if installed_bytes > 0 else 0,
            free_slots=0,
            installed_capacity_bytes=installed_bytes,
            max_capacity_bytes=None,
            slots=[],
            is_virtual_machine=engine.capabilities.is_virtual_machine,
            is_soldered=False,
            dmi_caveat=diag,
        )

        return ToolResult(
            tool_name=self.name,
            command_executed="unprivileged fallback (/proc/meminfo)",
            exit_code=0,
            raw_stdout=f"MemTotal bytes: {installed_bytes}",
            parsed=fallback_topology,
            duration_ms=0.5,
            provenance_tag="tool:get_memory_topology (unprivileged fallback)",
        )

    def parse_dmidecode_memory(self, stdout: str, is_vm: bool = False) -> MemoryTopology:
        """Parses 'dmidecode -t memory' output into structured MemoryTopology."""
        max_capacity_bytes: int | None = None
        slots: list[MemorySlot] = []
        is_soldered = False

        # Extract Maximum Capacity from Physical Memory Array block
        max_cap_match = re.search(
            r"Physical Memory Array\b(?:(?!Handle\b)[\s\S])*?Maximum Capacity:\s*([0-9.]+)\s*([A-Za-z]+)",
            stdout,
        )
        if max_cap_match:
            val = float(max_cap_match.group(1))
            unit = max_cap_match.group(2).upper()
            mult = 1024**3 if "GB" in unit else 1024**2 if "MB" in unit else 1024**4 if "TB" in unit else 1
            max_capacity_bytes = int(val * mult)

        # Extract individual Memory Device records
        device_blocks = re.split(r"\nHandle\s+0x[0-9A-Fa-f]+,\s+DMI type 17,", stdout)
        # Skip the header before the first Memory Device
        device_blocks = device_blocks[1:] if len(device_blocks) > 1 else []

        for block in device_blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            record: dict[str, str] = {}
            for line in lines:
                if ":" in line:
                    k, v = line.split(":", 1)
                    record[k.strip().lower()] = v.strip()

            locator = record.get("locator", f"Slot-{len(slots) + 1}")
            bank_locator = record.get("bank locator")
            size_str = record.get("size", "")
            form_factor = record.get("form factor", "Unknown")
            mem_type = record.get("type", "Unknown")
            mfr = record.get("manufacturer")

            # Check if soldered
            is_device_soldered = (
                "row of chips" in form_factor.lower()
                or "soldered" in locator.lower()
                or "embedded" in locator.lower()
                or "lpddr" in mem_type.lower()
            )
            if is_device_soldered:
                is_soldered = True

            # Speed
            speed_mts: int | None = None
            speed_str = record.get("speed", "")
            speed_match = re.search(r"(\d+)\s*(?:MT/s|MHz)", speed_str)
            if speed_match:
                speed_mts = int(speed_match.group(1))

            # Size determination
            size_bytes = 0
            is_empty = False
            if "no module installed" in size_str.lower() or size_str.strip() == "0 MB":
                is_empty = True
            else:
                sz_match = re.search(r"([0-9.]+)\s*([A-Za-z]+)", size_str)
                if sz_match:
                    num = float(sz_match.group(1))
                    unit = sz_match.group(2).upper()
                    m = 1024**3 if "GB" in unit else 1024**2 if "MB" in unit else 1
                    size_bytes = int(num * m)
                else:
                    is_empty = True

            slots.append(
                MemorySlot(
                    locator=locator,
                    bank_locator=bank_locator,
                    size_bytes=size_bytes,
                    form_factor=form_factor,
                    memory_type=mem_type,
                    speed_mts=speed_mts,
                    manufacturer=mfr if mfr and "unknown" not in mfr.lower() else None,
                    is_empty=is_empty,
                    is_soldered=is_device_soldered,
                )
            )

        total_slots = len(slots)
        used_slots = sum(1 for s in slots if not s.is_empty)
        free_slots = sum(1 for s in slots if s.is_empty)
        installed_capacity = sum(s.size_bytes for s in slots if not s.is_empty)

        # Build caveats for DMI inaccuracies, soldered RAM, or VMs
        caveat_parts = []
        if is_vm:
            caveat_parts.append(
                "System is executing inside a Virtual Machine. DMI max capacity and slot counts "
                "reflect hypervisor configuration rather than physical motherboard limits."
            )
        if is_soldered and free_slots == 0:
            caveat_parts.append(
                "Memory is soldered directly to the motherboard (e.g. LPDDR/Row of chips) with no "
                "available physical expansion slots."
            )
        if max_capacity_bytes and installed_capacity > max_capacity_bytes:
            caveat_parts.append(
                "Reported Maximum Capacity is lower than currently installed memory, indicating "
                "inaccurate BIOS DMI table values from the motherboard vendor."
            )

        dmi_caveat = " ".join(caveat_parts) if caveat_parts else None

        return MemoryTopology(
            total_slots=total_slots,
            used_slots=used_slots,
            free_slots=free_slots,
            installed_capacity_bytes=installed_capacity,
            max_capacity_bytes=max_capacity_bytes,
            slots=slots,
            is_virtual_machine=is_vm,
            is_soldered=is_soldered,
            dmi_caveat=dmi_caveat,
        )

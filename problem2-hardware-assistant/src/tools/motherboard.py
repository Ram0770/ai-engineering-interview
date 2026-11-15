"""Motherboard and BIOS inspection tool."""

from pathlib import Path
from typing import Any

from src.execution.engine import SafeExecutionEngine
from src.models.hardware import MotherboardInfo, ToolResult
from src.tools.base import BaseHardwareTool, EmptyParameters


class MotherboardTool(BaseHardwareTool):
    """Inspects motherboard manufacturer, model name, version, and BIOS firmware info."""

    name = "get_motherboard_bios_info"
    description = (
        "Retrieves motherboard manufacturer, product name, board revision, "
        "and BIOS firmware vendor, version, and release date."
    )
    parameters_schema = EmptyParameters

    def is_available(self, engine: SafeExecutionEngine) -> bool:
        return (
            Path("/sys/class/dmi/id").exists()
            or engine.capabilities.is_available("dmidecode")
        )

    def run(self, engine: SafeExecutionEngine, **kwargs: Any) -> ToolResult:
        # First priority: Unprivileged sysfs /sys/class/dmi/id/
        dmi_id_dir = Path("/sys/class/dmi/id")
        if dmi_id_dir.exists():
            try:
                board_mfr = self._read_sysfs(engine, dmi_id_dir / "board_vendor")
                board_name = self._read_sysfs(engine, dmi_id_dir / "board_name")
                board_ver = self._read_sysfs(engine, dmi_id_dir / "board_version")
                bios_vendor = self._read_sysfs(engine, dmi_id_dir / "bios_vendor")
                bios_ver = self._read_sysfs(engine, dmi_id_dir / "bios_version")
                bios_date = self._read_sysfs(engine, dmi_id_dir / "bios_date")

                if board_mfr or board_name or bios_vendor:
                    info = MotherboardInfo(
                        manufacturer=board_mfr or "Unknown",
                        product_name=board_name or "Unknown",
                        version=board_ver,
                        bios_vendor=bios_vendor,
                        bios_version=bios_ver,
                        bios_date=bios_date,
                    )
                    return ToolResult(
                        tool_name=self.name,
                        command_executed="read /sys/class/dmi/id/*",
                        exit_code=0,
                        raw_stdout=f"Board: {board_mfr} {board_name}, BIOS: {bios_vendor} {bios_ver}",
                        parsed=info,
                        duration_ms=0.5,
                        provenance_tag="tool:get_motherboard_bios_info (/sys/class/dmi/id)",
                    )
            except Exception:
                pass

        # Privileged fallback: dmidecode -t baseboard and -t bios
        if engine.capabilities.is_available("dmidecode"):
            res_board = engine.execute_command("dmidecode", ["-t", "baseboard"], use_sudo=True)
            res_bios = engine.execute_command("dmidecode", ["-t", "bios"], use_sudo=True)
            if res_board.exit_code == 0 or res_bios.exit_code == 0:
                parsed = self.parse_dmidecode(res_board.stdout, res_bios.stdout)
                return ToolResult(
                    tool_name=self.name,
                    command_executed="sudo -n dmidecode -t baseboard; sudo -n dmidecode -t bios",
                    exit_code=0,
                    raw_stdout=res_board.stdout + "\n" + res_bios.stdout,
                    parsed=parsed,
                    duration_ms=res_board.duration_ms + res_bios.duration_ms,
                    provenance_tag="tool:get_motherboard_bios_info (dmidecode)",
                )

        return ToolResult(
            tool_name=self.name,
            command_executed="read /sys/class/dmi/id",
            exit_code=127,
            raw_stdout="",
            error="Neither '/sys/class/dmi/id' nor 'dmidecode' is accessible.",
            provenance_tag="tool:get_motherboard_bios_info",
        )

    def _read_sysfs(self, engine: SafeExecutionEngine, path: Path) -> str | None:
        if path.exists():
            try:
                val = engine.read_virtual_file(path).strip()
                if val and val.lower() not in ("none", "unknown", "to be filled by o.e.m."):
                    return val
            except Exception:
                pass
        return None

    def parse_dmidecode(self, board_stdout: str, bios_stdout: str) -> MotherboardInfo:
        """Parses stdout of dmidecode baseboard and bios blocks."""
        board_mfr = "Unknown"
        board_name = "Unknown"
        board_ver = None
        bios_vendor = None
        bios_ver = None
        bios_date = None

        for line in board_stdout.splitlines():
            if ":" in line:
                k, v = [x.strip() for x in line.split(":", 1)]
                k_low = k.lower()
                if k_low == "manufacturer":
                    board_mfr = v
                elif k_low == "product name":
                    board_name = v
                elif k_low == "version":
                    board_ver = v

        for line in bios_stdout.splitlines():
            if ":" in line:
                k, v = [x.strip() for x in line.split(":", 1)]
                k_low = k.lower()
                if k_low == "vendor":
                    bios_vendor = v
                elif k_low == "version":
                    bios_ver = v
                elif k_low == "release date":
                    bios_date = v

        return MotherboardInfo(
            manufacturer=board_mfr,
            product_name=board_name,
            version=board_ver,
            bios_vendor=bios_vendor,
            bios_version=bios_ver,
            bios_date=bios_date,
        )

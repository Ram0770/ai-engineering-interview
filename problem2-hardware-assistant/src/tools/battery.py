"""Battery and power supply inspection tool reading sysfs power_supply."""

from pathlib import Path
from typing import Any

from src.execution.engine import SafeExecutionEngine
from src.models.hardware import BatteryInfo, ToolResult
from src.tools.base import BaseHardwareTool, EmptyParameters


class BatteryTool(BaseHardwareTool):
    """Inspects laptop battery status, charge percentage, health, and wear level."""

    name = "get_battery_info"
    description = (
        "Retrieves laptop battery status, current charge percentage, health/wear level, "
        "and AC power supply state from /sys/class/power_supply."
    )
    parameters_schema = EmptyParameters

    def is_available(self, engine: SafeExecutionEngine) -> bool:
        return Path("/sys/class/power_supply").exists()

    def run(self, engine: SafeExecutionEngine, **kwargs: Any) -> ToolResult:
        power_supply_dir = Path("/sys/class/power_supply")
        if not power_supply_dir.exists():
            return ToolResult(
                tool_name=self.name,
                command_executed="read /sys/class/power_supply",
                exit_code=0,
                raw_stdout="No /sys/class/power_supply directory found",
                parsed=BatteryInfo(
                    present=False,
                    status="No battery detected (Desktop / AC Mains / VM)",
                ),
                provenance_tag="tool:get_battery_info",
            )

        # Look for BAT0, BAT1, etc.
        bat_dirs = [p for p in power_supply_dir.iterdir() if p.name.startswith("BAT")]

        if not bat_dirs:
            return ToolResult(
                tool_name=self.name,
                command_executed="read /sys/class/power_supply",
                exit_code=0,
                raw_stdout="No BAT* directories found in /sys/class/power_supply",
                parsed=BatteryInfo(
                    present=False,
                    status="No battery installed (Desktop or VM)",
                ),
                provenance_tag="tool:get_battery_info (/sys/class/power_supply)",
            )

        bat = bat_dirs[0]
        status = self._read_sysfs_prop(engine, bat / "status") or "Unknown"
        capacity_str = self._read_sysfs_prop(engine, bat / "capacity")
        tech = self._read_sysfs_prop(engine, bat / "technology")
        cycles_str = self._read_sysfs_prop(engine, bat / "cycle_count")

        capacity_percent: int | None = None
        if capacity_str and capacity_str.isdigit():
            capacity_percent = int(capacity_str)

        # Health calculation: energy_full / energy_full_design or charge_full / charge_full_design
        health_percent: int | None = None
        full = self._read_numeric_prop(engine, bat / "energy_full") or self._read_numeric_prop(engine, bat / "charge_full")
        design = self._read_numeric_prop(engine, bat / "energy_full_design") or self._read_numeric_prop(engine, bat / "charge_full_design")
        if full and design and design > 0:
            health_percent = min(100, int((full / design) * 100))

        cycle_count: int | None = int(cycles_str) if cycles_str and cycles_str.isdigit() else None

        info = BatteryInfo(
            present=True,
            status=status,
            capacity_percent=capacity_percent,
            health_percent=health_percent,
            technology=tech,
            cycle_count=cycle_count,
        )

        return ToolResult(
            tool_name=self.name,
            command_executed=f"read {bat}",
            exit_code=0,
            raw_stdout=f"Battery {bat.name}: status={status}, capacity={capacity_percent}%",
            parsed=info,
            duration_ms=0.5,
            provenance_tag=f"tool:get_battery_info ({bat})",
        )

    def _read_sysfs_prop(self, engine: SafeExecutionEngine, path: Path) -> str | None:
        if path.exists():
            try:
                return engine.read_virtual_file(path).strip()
            except Exception:
                pass
        return None

    def _read_numeric_prop(self, engine: SafeExecutionEngine, path: Path) -> float | None:
        val = self._read_sysfs_prop(engine, path)
        if val:
            try:
                return float(val)
            except ValueError:
                pass
        return None

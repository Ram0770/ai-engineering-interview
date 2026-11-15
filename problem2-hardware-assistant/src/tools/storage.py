"""Storage block devices inspection tool distinguishing NVMe, SATA, and HDD."""

import json
from pathlib import Path
from typing import Any

from src.execution.engine import SafeExecutionEngine
from src.models.hardware import DriveType, StorageDevice, StorageInfo, ToolResult
from src.tools.base import BaseHardwareTool, EmptyParameters


class StorageTool(BaseHardwareTool):
    """Inspects storage block devices, partition layout, and media type (NVMe/SATA/HDD)."""

    name = "get_storage_devices"
    description = (
        "Retrieves disk drives, partition layouts, capacities, mountpoints, and transport "
        "protocols (distinguishing NVMe SSDs, SATA SSDs, and rotational HDDs)."
    )
    parameters_schema = EmptyParameters

    def is_available(self, engine: SafeExecutionEngine) -> bool:
        return engine.capabilities.is_available("lsblk") or Path("/sys/block").exists()

    def run(self, engine: SafeExecutionEngine, **kwargs: Any) -> ToolResult:
        if engine.capabilities.is_available("lsblk"):
            args = ["-J", "-b", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,ROTA,TRAN"]
            res = engine.execute_command("lsblk", args)
            if res.exit_code == 0:
                parsed = self.parse_lsblk_json(res.stdout)
                return ToolResult(
                    tool_name=self.name,
                    command_executed="lsblk " + " ".join(args),
                    exit_code=res.exit_code,
                    raw_stdout=res.stdout,
                    parsed=parsed,
                    duration_ms=res.duration_ms,
                    provenance_tag="tool:get_storage_devices (lsblk -J)",
                )

        # Fallback reading /sys/block
        sys_block = Path("/sys/block")
        if sys_block.exists():
            try:
                devices: list[StorageDevice] = []
                for entry in sys_block.iterdir():
                    name = entry.name
                    if name.startswith("loop") or name.startswith("ram"):
                        continue
                    size_file = entry / "size"
                    rota_file = entry / "queue" / "rotational"
                    size_bytes = 0
                    is_rota = False
                    if size_file.exists():
                        # sectors (512 bytes)
                        sectors = int(engine.read_virtual_file(size_file).strip() or "0")
                        size_bytes = sectors * 512
                    if rota_file.exists():
                        is_rota = engine.read_virtual_file(rota_file).strip() == "1"

                    tran = "nvme" if name.startswith("nvme") else "sata"
                    drive_type = self._determine_drive_type(tran, is_rota, name)
                    devices.append(
                        StorageDevice(
                            name=name,
                            size_bytes=size_bytes,
                            device_type="disk",
                            mountpoint=None,
                            model=None,
                            is_rotational=is_rota,
                            transport=tran,
                            drive_type=drive_type,
                        )
                    )
                return ToolResult(
                    tool_name=self.name,
                    command_executed="read /sys/block",
                    exit_code=0,
                    raw_stdout=f"Found {len(devices)} block devices in /sys/block",
                    parsed=StorageInfo(devices=devices),
                    duration_ms=1.0,
                    provenance_tag="tool:get_storage_devices (/sys/block)",
                )
            except Exception as e:
                return ToolResult(
                    tool_name=self.name,
                    command_executed="read /sys/block",
                    exit_code=-1,
                    raw_stdout="",
                    error=f"Failed to inspect /sys/block: {e}",
                    provenance_tag="tool:get_storage_devices",
                )

        return ToolResult(
            tool_name=self.name,
            command_executed="lsblk",
            exit_code=127,
            raw_stdout="",
            error="Neither 'lsblk' nor '/sys/block' is accessible.",
            provenance_tag="tool:get_storage_devices",
        )

    def parse_lsblk_json(self, stdout: str) -> StorageInfo:
        """Parses output from 'lsblk -J -b' into structured StorageInfo."""
        devices: list[StorageDevice] = []
        try:
            data = json.loads(stdout)
            blockdevices = data.get("blockdevices", [])
            self._flatten_devices(blockdevices, devices)
        except Exception:
            pass
        return StorageInfo(devices=devices)

    def _flatten_devices(self, raw_list: list[dict[str, Any]], output: list[StorageDevice]) -> None:
        """Recursively parses devices and their children partitions."""
        for item in raw_list:
            name = str(item.get("name", ""))
            if name.startswith("loop") or name.startswith("ram"):
                continue

            raw_size = item.get("size")
            size_bytes = 0
            if isinstance(raw_size, int):
                size_bytes = raw_size
            elif isinstance(raw_size, str) and raw_size.isdigit():
                size_bytes = int(raw_size)

            device_type = str(item.get("type", "disk"))
            mountpoint = item.get("mountpoint")
            model = item.get("model")
            if model:
                model = str(model).strip()

            raw_rota = item.get("rota")
            is_rota = False
            if isinstance(raw_rota, bool):
                is_rota = raw_rota
            elif str(raw_rota) in ("1", "true", "True"):
                is_rota = True

            tran = item.get("tran")
            if tran:
                tran = str(tran).lower().strip()
            elif name.startswith("nvme"):
                tran = "nvme"

            drive_type = self._determine_drive_type(tran, is_rota, name)

            output.append(
                StorageDevice(
                    name=name,
                    size_bytes=size_bytes,
                    device_type=device_type,
                    mountpoint=mountpoint,
                    model=model,
                    is_rotational=is_rota,
                    transport=tran,
                    drive_type=drive_type,
                )
            )

            # Process partition children
            children = item.get("children")
            if children and isinstance(children, list):
                self._flatten_devices(children, output)

    def _determine_drive_type(self, tran: Any, is_rota: bool, name: str) -> DriveType:
        """Categorizes drive as NVMe SSD, SATA SSD, HDD, or Removable."""
        if tran == "usb":
            return DriveType.REMOVABLE
        if tran == "nvme" or name.startswith("nvme"):
            return DriveType.NVME_SSD
        if is_rota:
            return DriveType.HDD
        if tran == "sata" and not is_rota:
            return DriveType.SATA_SSD
        if not is_rota:
            return DriveType.SATA_SSD
        return DriveType.UNKNOWN

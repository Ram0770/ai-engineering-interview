"""Validated Pydantic models for hardware domains."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DriveType(str, Enum):
    """Storage media category determined via TRAN & ROTA."""

    NVME_SSD = "NVMe SSD"
    SATA_SSD = "SATA SSD"
    HDD = "Hard Disk Drive (HDD)"
    REMOVABLE = "Removable / USB"
    UNKNOWN = "Unknown Drive Type"


class CPUInfo(BaseModel):
    """Processor architecture, cores, and frequency."""

    model_name: str = Field(..., description="CPU model brand and name")
    architecture: str = Field(..., description="Instruction set architecture (x86_64, aarch64, etc.)")
    sockets: int = Field(default=1, ge=1)
    cores_per_socket: int = Field(default=1, ge=1)
    threads_per_core: int = Field(default=1, ge=1)
    total_logical_cores: int = Field(..., ge=1)
    min_mhz: float | None = None
    max_mhz: float | None = None
    virtualization_flags: list[str] = Field(default_factory=list)


class MemorySummary(BaseModel):
    """System memory utilization snapshot."""

    total_bytes: int = Field(..., ge=0)
    used_bytes: int = Field(..., ge=0)
    free_bytes: int = Field(..., ge=0)
    available_bytes: int = Field(..., ge=0)
    swap_total_bytes: int = Field(default=0, ge=0)
    swap_used_bytes: int = Field(default=0, ge=0)
    swap_free_bytes: int = Field(default=0, ge=0)

    @property
    def total_gb(self) -> float:
        return round(self.total_bytes / (1024**3), 2)

    @property
    def used_gb(self) -> float:
        return round(self.used_bytes / (1024**3), 2)

    @property
    def free_gb(self) -> float:
        return round(self.free_bytes / (1024**3), 2)

    @property
    def available_gb(self) -> float:
        return round(self.available_bytes / (1024**3), 2)


class MemorySlot(BaseModel):
    """Physical or soldered DIMM memory slot specification."""

    locator: str = Field(..., description="Slot identifier on motherboard (e.g. ChannelA-DIMM0)")
    bank_locator: str | None = None
    size_bytes: int = Field(default=0, ge=0)
    form_factor: str = Field(default="Unknown", description="SODIMM, DIMM, Row of chips, etc.")
    memory_type: str = Field(default="Unknown", description="DDR4, DDR5, LPDDR4, LPDDR5, etc.")
    speed_mts: int | None = Field(default=None, description="Transfer speed in MT/s or MHz")
    manufacturer: str | None = None
    is_empty: bool = False
    is_soldered: bool = False

    @property
    def size_gb(self) -> float:
        return round(self.size_bytes / (1024**3), 2)


class MemoryTopology(BaseModel):
    """Board memory topology, installed RAM, slots, and max motherboard capacity."""

    total_slots: int = Field(..., ge=0)
    used_slots: int = Field(..., ge=0)
    free_slots: int = Field(..., ge=0)
    installed_capacity_bytes: int = Field(..., ge=0)
    max_capacity_bytes: int | None = Field(
        default=None,
        description="Maximum supported capacity reported by DMI or motherboard specs",
    )
    slots: list[MemorySlot] = Field(default_factory=list)
    is_virtual_machine: bool = False
    is_soldered: bool = False
    dmi_caveat: str | None = Field(
        default=None,
        description="Caveat regarding DMI table inaccuracies or soldered memory",
    )

    @property
    def installed_gb(self) -> float:
        return round(self.installed_capacity_bytes / (1024**3), 2)

    @property
    def max_capacity_gb(self) -> float | None:
        if self.max_capacity_bytes is not None:
            return round(self.max_capacity_bytes / (1024**3), 2)
        return None


class StorageDevice(BaseModel):
    """Storage block device (NVMe, SATA, HDD)."""

    name: str = Field(..., description="Device name e.g. nvme0n1, sda")
    size_bytes: int = Field(..., ge=0)
    device_type: str = Field(default="disk", description="disk, part, rom")
    mountpoint: str | None = None
    model: str | None = None
    is_rotational: bool = Field(default=False, description="ROTA=1 for HDD, 0 for SSD")
    transport: str | None = Field(default=None, description="TRAN=nvme, sata, usb")
    drive_type: DriveType = DriveType.UNKNOWN

    @property
    def size_gb(self) -> float:
        return round(self.size_bytes / (1024**3), 2)


class StorageInfo(BaseModel):
    """Collection of system storage block devices."""

    devices: list[StorageDevice] = Field(default_factory=list)


class GPUDevice(BaseModel):
    """Graphics processing unit specification."""

    vendor: str = Field(..., description="NVIDIA, AMD, Intel")
    model: str = Field(...)
    pci_slot: str | None = None
    vram_bytes: int | None = None
    driver_version: str | None = None

    @property
    def vram_gb(self) -> float | None:
        if self.vram_bytes is not None:
            return round(self.vram_bytes / (1024**3), 2)
        return None


class GPUInfo(BaseModel):
    """Host graphics devices."""

    devices: list[GPUDevice] = Field(default_factory=list)


class BatteryInfo(BaseModel):
    """Laptop power supply and battery health status."""

    present: bool = True
    status: str = Field(default="Unknown", description="Charging, Discharging, Full, Not charging")
    capacity_percent: int | None = Field(default=None, ge=0, le=100)
    health_percent: int | None = Field(default=None, ge=0, le=100)
    technology: str | None = None
    cycle_count: int | None = None


class OSKernelInfo(BaseModel):
    """Operating system release, kernel, and system uptime."""

    os_name: str = Field(..., description="e.g. Ubuntu, Fedora Linux, Debian GNU/Linux")
    os_version: str = Field(default="")
    kernel_release: str = Field(..., description="e.g. 6.8.0-45-generic")
    kernel_architecture: str = Field(default="x86_64")
    hostname: str = Field(default="localhost")
    uptime_seconds: float = Field(default=0.0, ge=0.0)


class MotherboardInfo(BaseModel):
    """Motherboard and system BIOS hardware specifications."""

    manufacturer: str = Field(default="Unknown")
    product_name: str = Field(default="Unknown")
    version: str | None = None
    bios_vendor: str | None = None
    bios_version: str | None = None
    bios_date: str | None = None


class HardwareFact(BaseModel):
    """Provenance-tracked atomic hardware observation."""

    entity: str
    attribute: str
    value: str | int | float | bool | None
    tool_name: str
    command_executed: str


class ToolResult(BaseModel):
    """Envelope for all hardware tool executions."""

    tool_name: str
    command_executed: str
    exit_code: int
    raw_stdout: str
    parsed: Any | None = None
    error: str | None = None
    duration_ms: float = 0.0
    provenance_tag: str = Field(..., description="Tag identifying tool and execution command")

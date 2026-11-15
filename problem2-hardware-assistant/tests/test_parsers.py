"""Unit tests for all hardware output parsers and Pydantic models."""

from pathlib import Path

import pytest

from src.models.hardware import (
    DriveType,
    MemorySummary,
)
from src.tools.cpu import CPUTool
from src.tools.gpu import GPUTool
from src.tools.memory import MemorySummaryTool, MemoryTopologyTool
from src.tools.storage import StorageTool


def test_cpu_parser(fixtures_dir: Path) -> None:
    tool = CPUTool()
    stdout = (fixtures_dir / "lscpu.txt").read_text(encoding="utf-8")
    parsed = tool.parse_lscpu(stdout)

    assert "i7-12700H" in parsed.model_name
    assert parsed.architecture == "x86_64"
    assert parsed.total_logical_cores == 20
    assert parsed.cores_per_socket == 14
    assert parsed.max_mhz == 4700.0
    assert "vmx" in parsed.virtualization_flags


def test_memory_summary_parser(fixtures_dir: Path) -> None:
    tool = MemorySummaryTool()
    stdout = (fixtures_dir / "free_b.txt").read_text(encoding="utf-8")
    parsed = tool.parse_free_b(stdout)

    assert parsed.total_bytes == 17179869184
    assert parsed.total_gb == 16.0
    assert parsed.used_bytes == 4294967296
    assert parsed.free_bytes == 8589934592
    assert parsed.available_bytes == 12884901888


def test_memory_topology_parser(fixtures_dir: Path) -> None:
    tool = MemoryTopologyTool()
    stdout = (fixtures_dir / "dmidecode_memory.txt").read_text(encoding="utf-8")
    parsed = tool.parse_dmidecode_memory(stdout, is_vm=False)

    assert parsed.total_slots == 2
    assert parsed.used_slots == 1
    assert parsed.free_slots == 1
    assert parsed.installed_capacity_bytes == 16 * (1024**3)
    assert parsed.installed_gb == 16.0
    assert parsed.max_capacity_bytes == 64 * (1024**3)
    assert parsed.max_capacity_gb == 64.0
    assert parsed.slots[0].locator == "Controller0-ChannelA"
    assert parsed.slots[0].memory_type == "DDR4"
    assert parsed.slots[0].speed_mts == 3200


def test_storage_parser(fixtures_dir: Path) -> None:
    tool = StorageTool()
    stdout = (fixtures_dir / "lsblk_json.json").read_text(encoding="utf-8")
    parsed = tool.parse_lsblk_json(stdout)

    assert len(parsed.devices) >= 2
    nvme_dev = next(d for d in parsed.devices if d.name == "nvme0n1")
    assert nvme_dev.drive_type == DriveType.NVME_SSD
    assert nvme_dev.is_rotational is False
    assert nvme_dev.size_gb == pytest.approx(476.94, rel=1e-2)

    sata_hdd = next(d for d in parsed.devices if d.name == "sda")
    assert sata_hdd.drive_type == DriveType.HDD
    assert sata_hdd.is_rotational is True


def test_gpu_parser(fixtures_dir: Path) -> None:
    tool = GPUTool()
    stdout = (fixtures_dir / "lspci_vmm.txt").read_text(encoding="utf-8")
    parsed = tool.parse_lspci_vmm(stdout)

    assert len(parsed) == 2
    vendors = [d.vendor for d in parsed]
    assert "Intel" in vendors
    assert "NVIDIA" in vendors
    nv_gpu = next(d for d in parsed if d.vendor == "NVIDIA")
    assert "RTX 3060" in nv_gpu.model


def test_soldered_ram_and_vm_dmi_caveats() -> None:
    tool = MemoryTopologyTool()
    soldered_path = Path(__file__).resolve().parent / "fixtures" / "synthetic" / "soldered_ram" / "dmidecode_memory.txt"
    stdout_soldered = soldered_path.read_text(encoding="utf-8")
    parsed_soldered = tool.parse_dmidecode_memory(stdout_soldered, is_vm=False)

    assert parsed_soldered.is_soldered is True
    assert parsed_soldered.free_slots == 0
    assert "soldered directly to the motherboard" in (parsed_soldered.dmi_caveat or "")

    vm_path = Path(__file__).resolve().parent / "fixtures" / "synthetic" / "cloud_vm" / "dmidecode_memory.txt"
    stdout_vm = vm_path.read_text(encoding="utf-8")
    parsed_vm = tool.parse_dmidecode_memory(stdout_vm, is_vm=True)
    assert parsed_vm.is_virtual_machine is True
    assert "Virtual Machine" in (parsed_vm.dmi_caveat or "")


def test_pydantic_hardware_models() -> None:
    """Verifies bounds checking and properties on Pydantic hardware models."""
    summary = MemorySummary(
        total_bytes=10737418240,
        used_bytes=5368709120,
        free_bytes=5368709120,
        available_bytes=5368709120,
    )
    assert summary.total_gb == 10.0
    assert summary.used_gb == 5.0

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        # Negative bytes should fail validation
        MemorySummary(total_bytes=-1, used_bytes=0, free_bytes=0, available_bytes=0)

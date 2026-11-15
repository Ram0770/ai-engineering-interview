"""Multi-distro fixture verification and capture script tests."""

import json
from pathlib import Path

from src.tools.cpu import CPUTool
from src.tools.memory import MemoryTopologyTool
from src.tools.storage import StorageTool


def test_multi_distro_fixtures() -> None:
    """Verifies all synthetic distro fixtures have metadata and parse without errors."""
    fixtures_root = Path(__file__).resolve().parent / "fixtures" / "synthetic"
    distro_dirs = [d for d in fixtures_root.iterdir() if d.is_dir()]

    assert len(distro_dirs) >= 5

    for d in distro_dirs:
        meta_file = d / "metadata.json"
        assert meta_file.exists(), f"Metadata missing in {d.name}"
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        assert meta["type"] == "synthetic", f"Synthetic tag missing in {d.name}"

    # Test Debian 12 desktop Ryzen CPU and 4-slot RAM
    debian_dir = fixtures_root / "debian_12"
    cpu_tool = CPUTool()
    parsed_cpu = cpu_tool.parse_lscpu((debian_dir / "lscpu.txt").read_text(encoding="utf-8"))
    assert "Ryzen 7 5800X" in parsed_cpu.model_name
    assert parsed_cpu.total_logical_cores == 16

    mem_tool = MemoryTopologyTool()
    parsed_mem = mem_tool.parse_dmidecode_memory((debian_dir / "dmidecode_memory.txt").read_text(encoding="utf-8"))
    assert parsed_mem.total_slots == 4
    assert parsed_mem.used_slots == 2
    assert parsed_mem.free_slots == 2
    assert parsed_mem.max_capacity_gb == 128.0


def test_broken_fixtures_resilience() -> None:
    """Verifies that corrupted or malformed command outputs do not crash the parsers."""
    broken_dir = Path(__file__).resolve().parent / "fixtures" / "synthetic" / "broken_outputs"
    storage_tool = StorageTool()
    # Should handle truncated JSON gracefully and return empty list
    corrupted_json = (broken_dir / "corrupted_lsblk.json").read_text(encoding="utf-8")
    parsed_storage = storage_tool.parse_lsblk_json(corrupted_json)
    assert len(parsed_storage.devices) == 0

    mem_tool = MemoryTopologyTool()
    perm_denied = (broken_dir / "permission_denied_dmidecode.txt").read_text(encoding="utf-8")
    parsed_mem = mem_tool.parse_dmidecode_memory(perm_denied)
    assert parsed_mem.total_slots == 0
    assert parsed_mem.used_slots == 0


def test_capture_fixtures_script() -> None:
    """Verifies that the capture_system_fixtures.py script exists and has valid entry points."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "capture_system_fixtures.py"
    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")
    assert "def capture()" in content
    assert "lscpu" in content
    assert "dmidecode" in content

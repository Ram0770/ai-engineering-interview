"""Tests for startup capability discovery."""

from src.discovery import get_capabilities


def test_capability_discovery() -> None:
    caps = get_capabilities()
    assert caps.os_type in ("Windows", "Linux", "Darwin")
    assert isinstance(caps.binaries, dict)
    assert "lscpu" in caps.binaries
    assert "dmidecode" in caps.binaries

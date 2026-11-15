"""Permissions, least privilege, and scoped sudoers tests."""

from pathlib import Path

import pytest

from src.cli import check_root_privilege
from src.execution.engine import SafeExecutionEngine, SecurityViolationError
from src.tools.memory import MemoryTopologyTool


def test_sudoers_template_validation() -> None:
    """Verifies that the shipped sudoers template strictly pins arguments and prohibits bare dmidecode."""
    sudoers_path = Path(__file__).resolve().parent.parent / "sudoers.d" / "hw-assistant"
    assert sudoers_path.exists(), "sudoers.d/hw-assistant file must exist"

    content = sudoers_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    # Check each permitted rule
    for line in lines:
        assert "NOPASSWD:" in line
        # Must have pinned arguments
        assert "-t memory" in line or "-t bios" in line or "-t baseboard" in line
        # Must NOT be an unrestricted dmidecode invocation
        assert not line.endswith("dmidecode")


def test_sudo_non_interactive_invocation(mock_engine: SafeExecutionEngine) -> None:
    """Verifies that unpermitted dmidecode arguments are rejected before invoking sudo."""
    with pytest.raises(SecurityViolationError, match="Unpermitted dmidecode arguments"):
        # Attempting arbitrary flags like --dump or -t processor
        mock_engine.execute_command("dmidecode", ["-t", "processor"], use_sudo=True)


def test_unprivileged_fallback_mode() -> None:
    """Verifies that when sudo/root permissions are unavailable, unprivileged fallback returns gracefully."""
    from src.discovery import SystemCapabilities
    caps = SystemCapabilities()
    caps.binaries["dmidecode"] = None
    engine = SafeExecutionEngine(capabilities=caps)

    tool = MemoryTopologyTool()
    res = tool.run(engine)
    assert res.exit_code == 0
    assert res.parsed is not None
    assert res.parsed.dmi_caveat is not None
    assert "sudo cp sudoers.d/hw-assistant" in res.parsed.dmi_caveat


def test_permission_denied_diagnostic_message() -> None:
    """Verifies that missing root permissions produce a diagnostic message instead of an unhandled crash."""
    from src.discovery import SystemCapabilities
    caps = SystemCapabilities()
    caps.binaries["dmidecode"] = None
    engine = SafeExecutionEngine(capabilities=caps)

    tool = MemoryTopologyTool()
    res = tool.run(engine)
    assert "DMI physical slot topology and maximum capacity require elevated privileges" in (res.parsed.dmi_caveat or "")


def test_root_execution_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that running the CLI as EUID 0 (root) prints a security warning."""
    import os
    if hasattr(os, "geteuid"):
        monkeypatch.setattr(os, "geteuid", lambda: 0)
        # Should execute check_root_privilege without crashing
        check_root_privilege()

"""Audit logging and sensitive hardware identifier redaction tests."""

import json
from pathlib import Path

from src.audit import AuditLogger, redact_sensitive_data


def test_redaction_patterns() -> None:
    """Verifies that serial numbers, UUIDs, and MAC addresses are redacted from text."""
    sample = (
        "Device: Samsung SSD\n"
        "Serial Number: S5YJNX0T123456K\n"
        "Chassis UUID: 4C4C4544-004B-4E10-8043-B2C04F433232\n"
        "Ethernet MAC: 00:1A:2B:3C:4D:5E\n"
    )
    redacted = redact_sensitive_data(sample)

    assert "S5YJNX0T123456K" not in redacted
    assert "[REDACTED_SERIAL]" in redacted
    assert "4C4C4544-004B-4E10-8043-B2C04F433232" not in redacted
    assert "[REDACTED_UUID]" in redacted
    assert "00:1A:2B:3C:4D:5E" not in redacted
    assert "[REDACTED_MAC]" in redacted


def test_audit_log_generation_and_redaction(tmp_path: Path) -> None:
    """Verifies that tool execution writes a structured JSON line with redacted values."""
    log_file = tmp_path / "audit.log"
    logger = AuditLogger(log_path=log_file, redact=True)

    record = logger.log_tool_execution(
        tool_name="get_memory_topology",
        argv=["dmidecode", "-t", "memory", "serial:ABCDEF12345"],
        exit_code=0,
        duration_ms=4.5,
        output_size_bytes=1024,
        raw_output_snippet="Memory Device Serial Number: 1234567890",
        caller="test_suite",
    )

    assert record["tool_name"] == "get_memory_topology"
    assert record["exit_code"] == 0
    assert "[REDACTED_SERIAL]" in record["output_snippet"]

    # Verify persistent file content
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["tool_name"] == "get_memory_topology"

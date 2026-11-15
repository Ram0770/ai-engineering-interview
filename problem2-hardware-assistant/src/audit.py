"""Audit logging service for all hardware tool executions."""

import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("hw_assistant.audit")

# Patterns matching sensitive hardware identifiers that should be redacted
REDACTION_PATTERNS = [
    # Serial numbers: "Serial Number: 12345ABC", "serial: 12345ABC"
    (re.compile(r"(?i)(serial\s*(?:number)?[:=]\s*)([A-Za-z0-9_-]{4,})"), r"\1[REDACTED_SERIAL]"),
    # UUIDs: "UUID: 4C4C4544-004B-4E10-8043-B2C04F433232"
    (
        re.compile(
            r"(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        ),
        "[REDACTED_UUID]",
    ),
    # MAC addresses: 00:1A:2B:3C:4D:5E or 00-1A-2B-3C-4D-5E
    (re.compile(r"(?i)\b([0-9a-f]{2}[:-]){5}([0-9a-f]{2})\b"), "[REDACTED_MAC]"),
]


def redact_sensitive_data(text: str) -> str:
    """Redacts hardware serial numbers, UUIDs, and MAC addresses from raw text."""
    redacted = text
    for pattern, replacement in REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class AuditLogger:
    """Thread-safe append-only structured audit logger for tool calls."""

    def __init__(self, log_path: Path | None = None, redact: bool = True) -> None:
        self.log_path = log_path or Path("audit.log")
        self.redact = redact
        self._lock = threading.Lock()

    def log_tool_execution(
        self,
        tool_name: str,
        argv: list[str],
        exit_code: int,
        duration_ms: float,
        output_size_bytes: int,
        raw_output_snippet: str,
        error: str | None = None,
        caller: str = "orchestrator",
    ) -> dict[str, Any]:
        """Records an execution event to the structured audit log."""
        snippet = raw_output_snippet[:500]
        if self.redact:
            snippet = redact_sensitive_data(snippet)
            clean_argv = [redact_sensitive_data(arg) for arg in argv]
        else:
            clean_argv = list(argv)

        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "caller": caller,
            "tool_name": tool_name,
            "argv": clean_argv,
            "exit_code": exit_code,
            "duration_ms": round(duration_ms, 2),
            "output_size_bytes": output_size_bytes,
            "output_snippet": snippet,
            "error": error,
        }

        entry_line = json.dumps(record) + "\n"

        with self._lock:
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(entry_line)
            except OSError as e:
                logger.error(f"Failed to write to audit log {self.log_path}: {e}")

        return record

"""Safe, sandboxed execution engine for hardware inspection commands."""

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from src.audit import AuditLogger
from src.config import settings
from src.discovery import SystemCapabilities, get_capabilities

# Dangerous shell characters that must never appear in arguments
DANGEROUS_CHARS = re.compile(r"[;&|`$<>\n\r\x00]")

# Strict allowed arguments for dmidecode (matching pinned sudoers rules)
DMIDECODE_ALLOWED_TYPE_ARGS = {"memory", "bios", "baseboard"}

# Safe device name pattern (e.g. sda, nvme0n1, pci0000:00)
SAFE_DEVICE_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.:]+$")


@dataclass
class ExecutionResult:
    """Outcome of a safe command execution."""

    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    output_capped: bool = False
    error_message: str | None = None


class SecurityViolationError(Exception):
    """Raised when an execution violates sandboxing or security invariants."""

    pass


class SafeExecutionEngine:
    """Enforces execution invariants: shell=False, fixed binary paths, timeouts, and sanitized env."""

    def __init__(
        self,
        capabilities: SystemCapabilities | None = None,
        audit_logger: AuditLogger | None = None,
        timeout_seconds: float | None = None,
        max_output_bytes: int | None = None,
    ) -> None:
        self.capabilities = capabilities or get_capabilities()
        self.audit_logger = audit_logger or AuditLogger(settings.audit_log_path)
        self.timeout_seconds = timeout_seconds or settings.execution_timeout_seconds
        self.max_output_bytes = max_output_bytes or settings.max_output_bytes

    def sanitize_environment(self) -> dict[str, str]:
        """Produces a minimal, deterministic environment preventing ambient variable leaks."""
        return {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LC_ALL": "C",
            "LANG": "C",
            "TERM": "dumb",
        }

    def validate_argument(self, arg: str) -> None:
        """Validates that a single command-line argument contains no injection payloads."""
        if DANGEROUS_CHARS.search(arg):
            raise SecurityViolationError(
                f"Malicious characters detected in argument: {arg!r}"
            )
        if ".." in arg:
            raise SecurityViolationError(
                f"Path traversal detected in argument: {arg!r}"
            )

    def execute_command(
        self,
        binary_name: str,
        args: list[str],
        use_sudo: bool = False,
        caller: str = "orchestrator",
    ) -> ExecutionResult:
        """Executes an allow-listed binary with shell=False, timeouts, and output capping."""
        # 1. Security Check: Binary name & Argument validation
        self.validate_argument(binary_name)
        for arg in args:
            self.validate_argument(arg)

        # 2. Path Resolution: Discovered absolute path
        resolved_bin = self.capabilities.get_binary_path(binary_name)
        if not resolved_bin:
            err = f"Binary '{binary_name}' is not installed or available on the host."
            return ExecutionResult(
                argv=[binary_name] + args,
                exit_code=127,
                stdout="",
                stderr=err,
                duration_ms=0.0,
                error_message=err,
            )

        # 3. Privilege Escalation Check: Use sudo -n with pinned arguments
        final_argv: list[str] = []
        if use_sudo:
            sudo_bin = self.capabilities.get_binary_path("sudo")
            if not sudo_bin:
                err = "sudo requested but not found in PATH."
                return ExecutionResult(
                    argv=[binary_name] + args,
                    exit_code=126,
                    stdout="",
                    stderr=err,
                    duration_ms=0.0,
                    error_message=err,
                )

            # Security validation for dmidecode arguments
            if binary_name == "dmidecode":
                # Must match pinned sudoers: -t <type>
                if len(args) != 2 or args[0] != "-t" or args[1] not in DMIDECODE_ALLOWED_TYPE_ARGS:
                    raise SecurityViolationError(
                        f"Unpermitted dmidecode arguments: {args!r}. "
                        f"Must be '-t memory', '-t bios', or '-t baseboard'."
                    )

            final_argv = [sudo_bin, "-n", resolved_bin] + args
        else:
            final_argv = [resolved_bin] + args

        # 4. Sandboxed Invocation
        clean_env = self.sanitize_environment()
        start_time = time.perf_counter()
        capped = False

        try:
            # Strict shell=False is enforced via list passing and explicit flag
            process = subprocess.Popen(
                final_argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                shell=False,
                env=clean_env,
                text=False,
            )

            try:
                raw_out, raw_err = process.communicate(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                err_msg = f"Command timed out after {self.timeout_seconds}s"
                self.audit_logger.log_tool_execution(
                    tool_name=binary_name,
                    argv=final_argv,
                    exit_code=-1,
                    duration_ms=duration_ms,
                    output_size_bytes=0,
                    raw_output_snippet="",
                    error=err_msg,
                    caller=caller,
                )
                return ExecutionResult(
                    argv=final_argv,
                    exit_code=-1,
                    stdout="",
                    stderr=err_msg,
                    duration_ms=duration_ms,
                    error_message=err_msg,
                )

            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # 5. Output size capping
            if len(raw_out) > self.max_output_bytes:
                raw_out = raw_out[: self.max_output_bytes]
                capped = True

            out_str = raw_out.decode("utf-8", errors="replace")
            err_str = raw_err.decode("utf-8", errors="replace")

            # 6. Audit Logging
            self.audit_logger.log_tool_execution(
                tool_name=binary_name,
                argv=final_argv,
                exit_code=process.returncode,
                duration_ms=duration_ms,
                output_size_bytes=len(raw_out),
                raw_output_snippet=out_str,
                error=err_str if process.returncode != 0 else None,
                caller=caller,
            )

            return ExecutionResult(
                argv=final_argv,
                exit_code=process.returncode,
                stdout=out_str,
                stderr=err_str,
                duration_ms=duration_ms,
                output_capped=capped,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"Subprocess execution failed: {str(e)}"
            self.audit_logger.log_tool_execution(
                tool_name=binary_name,
                argv=final_argv,
                exit_code=-1,
                duration_ms=duration_ms,
                output_size_bytes=0,
                raw_output_snippet="",
                error=err_msg,
                caller=caller,
            )
            return ExecutionResult(
                argv=final_argv,
                exit_code=-1,
                stdout="",
                stderr=err_msg,
                duration_ms=duration_ms,
                error_message=err_msg,
            )

    def read_virtual_file(
        self,
        file_path: Path,
        max_bytes: int | None = None,
        caller: str = "orchestrator",
    ) -> str:
        """Safely reads a virtual sysfs or procfs file with path traversal prevention."""
        resolved = file_path.resolve()
        path_str = str(resolved).replace("\\", "/")

        # Strict containment check: must be inside /proc or /sys
        if not (path_str.startswith("/proc") or path_str.startswith("/sys")):
            raise SecurityViolationError(
                f"Access denied: Path {path_str} is not in /proc or /sys."
            )

        limit = max_bytes or self.max_output_bytes
        start_time = time.perf_counter()

        try:
            with open(resolved, "rb") as f:
                data = f.read(limit)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            text = data.decode("utf-8", errors="replace")
            self.audit_logger.log_tool_execution(
                tool_name=f"read:{file_path.name}",
                argv=["read", str(resolved)],
                exit_code=0,
                duration_ms=duration_ms,
                output_size_bytes=len(data),
                raw_output_snippet=text,
                caller=caller,
            )
            return text
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.audit_logger.log_tool_execution(
                tool_name=f"read:{file_path.name}",
                argv=["read", str(resolved)],
                exit_code=-1,
                duration_ms=duration_ms,
                output_size_bytes=0,
                raw_output_snippet="",
                error=str(e),
                caller=caller,
            )
            raise

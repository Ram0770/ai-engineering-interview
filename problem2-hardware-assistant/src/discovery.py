"""System capability discovery and path resolution."""

import os
import platform
import shutil
import subprocess
from pathlib import Path


class SystemCapabilities:
    """Discovered system capabilities, resolved binary paths, and environment features."""

    def __init__(self) -> None:
        self.os_type: str = platform.system()
        self.is_linux: bool = self.os_type == "Linux"
        self.is_windows: bool = self.os_type == "Windows"
        self.is_darwin: bool = self.os_type == "Darwin"

        self.binaries: dict[str, str | None] = {}
        self.sysfs_available: bool = False
        self.procfs_available: bool = False
        self.has_sudo_nopasswd_dmidecode: bool = False
        self.is_virtual_machine: bool = False

        self._discover()

    def _discover(self) -> None:
        """Probes the current host environment for binaries and virtual filesystems."""
        standard_tools = [
            "lscpu",
            "lsblk",
            "free",
            "lspci",
            "nvidia-smi",
            "uname",
            "dmidecode",
            "sudo",
        ]

        # Prioritize standard system sbin locations for administrative tools
        custom_search_paths = [
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        ]
        path_env = os.pathsep.join(custom_search_paths) + os.pathsep + os.environ.get("PATH", "")

        for tool in standard_tools:
            resolved = shutil.which(tool, path=path_env)
            self.binaries[tool] = resolved

        # Check virtual filesystems
        self.procfs_available = Path("/proc/cpuinfo").exists() and Path("/proc/meminfo").exists()
        self.sysfs_available = Path("/sys/class").exists()

        # Check if running in a VM (heuristics: DMI sysfs or hypervisor flags)
        if self.sysfs_available:
            sys_vendor_path = Path("/sys/class/dmi/id/sys_vendor")
            product_name_path = Path("/sys/class/dmi/id/product_name")
            try:
                if sys_vendor_path.exists():
                    vendor = sys_vendor_path.read_text(encoding="utf-8").lower()
                    if any(vm_tag in vendor for vm_tag in ["qemu", "kvm", "vmware", "virtualbox", "xen"]):
                        self.is_virtual_machine = True
                if product_name_path.exists():
                    prod = product_name_path.read_text(encoding="utf-8").lower()
                    if any(vm_tag in prod for vm_tag in ["standard pc", "virtual machine", "kvm", "virtualbox"]):
                        self.is_virtual_machine = True
            except OSError:
                pass

        # Check sudo non-interactive capability for dmidecode if dmidecode and sudo are present
        sudo_bin = self.binaries.get("sudo")
        dmidecode_bin = self.binaries.get("dmidecode")
        if self.is_linux and sudo_bin and dmidecode_bin:
            try:
                # Test with sudo -n dmidecode -t memory
                proc = subprocess.run(
                    ["sudo", "-n", dmidecode_bin, "-t", "memory"],
                    capture_output=True,
                    timeout=1.0,
                )
                if proc.returncode == 0:
                    self.has_sudo_nopasswd_dmidecode = True
            except (subprocess.SubprocessError, OSError):
                self.has_sudo_nopasswd_dmidecode = False

    def get_binary_path(self, tool_name: str) -> str | None:
        """Returns the absolute resolved path of a discovered binary, or None if absent."""
        return self.binaries.get(tool_name)

    def is_available(self, tool_name: str) -> bool:
        """Checks if a binary is discovered on the host."""
        return self.binaries.get(tool_name) is not None

    @property
    def available_tools(self) -> set[str]:
        """Set of available standard binary names."""
        return {k for k, v in self.binaries.items() if v is not None}


# Singleton instance
_capabilities: SystemCapabilities | None = None


def get_capabilities(refresh: bool = False) -> SystemCapabilities:
    """Returns or refreshes the global discovered system capabilities."""
    global _capabilities
    if _capabilities is None or refresh:
        _capabilities = SystemCapabilities()
    return _capabilities

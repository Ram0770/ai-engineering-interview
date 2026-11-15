"""GPU inspection tool supporting lspci and nvidia-smi."""

from pathlib import Path
from typing import Any

from src.execution.engine import SafeExecutionEngine
from src.models.hardware import GPUDevice, GPUInfo, ToolResult
from src.tools.base import BaseHardwareTool, EmptyParameters


class GPUTool(BaseHardwareTool):
    """Inspects graphics processors, integrated GPUs, and discrete video adapters."""

    name = "get_gpu_info"
    description = (
        "Retrieves graphics controllers and discrete GPU details (NVIDIA, AMD, Intel), "
        "including model name, PCI slot, driver version, and video memory (VRAM)."
    )
    parameters_schema = EmptyParameters

    def is_available(self, engine: SafeExecutionEngine) -> bool:
        return (
            engine.capabilities.is_available("lspci")
            or engine.capabilities.is_available("nvidia-smi")
            or Path("/sys/bus/pci/devices").exists()
        )

    def run(self, engine: SafeExecutionEngine, **kwargs: Any) -> ToolResult:
        devices: list[GPUDevice] = []
        commands_run: list[str] = []

        # 1. Query lspci -vmm for all PCI display / 3D controllers
        if engine.capabilities.is_available("lspci"):
            res = engine.execute_command("lspci", ["-vmm"])
            commands_run.append("lspci -vmm")
            if res.exit_code == 0:
                pci_gpus = self.parse_lspci_vmm(res.stdout)
                devices.extend(pci_gpus)

        # 2. Check nvidia-smi for discrete NVIDIA GPU telemetry
        if engine.capabilities.is_available("nvidia-smi"):
            nv_args = ["--query-gpu=gpu_name,memory.total,driver_version", "--format=csv,noheader,nounits"]
            res_nv = engine.execute_command("nvidia-smi", nv_args)
            commands_run.append("nvidia-smi")
            if res_nv.exit_code == 0 and res_nv.stdout.strip():
                nv_gpus = self.parse_nvidia_smi(res_nv.stdout)
                # Merge or complement
                if nv_gpus:
                    # If lspci found generic nvidia, replace with rich nvidia-smi details
                    devices = [d for d in devices if "nvidia" not in d.vendor.lower()]
                    devices.extend(nv_gpus)

        if not devices and not commands_run:
            return ToolResult(
                tool_name=self.name,
                command_executed="lspci",
                exit_code=127,
                raw_stdout="",
                error="Neither 'lspci' nor 'nvidia-smi' is available to inspect GPUs.",
                provenance_tag="tool:get_gpu_info",
            )

        return ToolResult(
            tool_name=self.name,
            command_executed="; ".join(commands_run) if commands_run else "none",
            exit_code=0,
            raw_stdout=f"Detected {len(devices)} GPU(s)",
            parsed=GPUInfo(devices=devices),
            duration_ms=1.0,
            provenance_tag=f"tool:get_gpu_info ({', '.join(commands_run)})",
        )

    def parse_lspci_vmm(self, stdout: str) -> list[GPUDevice]:
        """Parses machine-readable 'lspci -vmm' records."""
        devices: list[GPUDevice] = []
        # Records separated by double newlines
        blocks = stdout.strip().split("\n\n")

        for block in blocks:
            props: dict[str, str] = {}
            for line in block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    props[k.strip().lower()] = v.strip()

            class_name = props.get("class", "").lower()
            if any(term in class_name for term in ["vga compatible controller", "3d controller", "display controller"]):
                vendor = props.get("vendor", "Unknown")
                device_name = props.get("device", "Unknown GPU")
                slot = props.get("slot")

                # Clean vendor name
                clean_vendor = vendor
                if "nvidia" in vendor.lower() or "nvidia" in device_name.lower():
                    clean_vendor = "NVIDIA"
                elif "advanced micro devices" in vendor.lower() or "amd" in vendor.lower():
                    clean_vendor = "AMD"
                elif "intel" in vendor.lower():
                    clean_vendor = "Intel"

                devices.append(
                    GPUDevice(
                        vendor=clean_vendor,
                        model=device_name,
                        pci_slot=slot,
                        vram_bytes=None,
                        driver_version=None,
                    )
                )

        return devices

    def parse_nvidia_smi(self, stdout: str) -> list[GPUDevice]:
        """Parses 'nvidia-smi --query-gpu=... --format=csv,noheader,nounits'."""
        devices: list[GPUDevice] = []
        for line in stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                name, mem_str, driver = parts[0], parts[1], parts[2]
                vram_bytes = None
                try:
                    # mem_str is in MiB
                    vram_bytes = int(float(mem_str)) * 1024 * 1024
                except ValueError:
                    pass

                devices.append(
                    GPUDevice(
                        vendor="NVIDIA",
                        model=name,
                        pci_slot=None,
                        vram_bytes=vram_bytes,
                        driver_version=driver,
                    )
                )
        return devices

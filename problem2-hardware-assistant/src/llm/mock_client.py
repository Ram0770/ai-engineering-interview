"""Deterministic Mock LLM client for offline unit and integration testing."""

import json
from typing import Any

from src.llm.base import ChatMessage, ChatResponse, LLMClient, ToolCall


class MockLLMClient(LLMClient):
    """Deterministic, configurable mock LLM providing heuristic tool selection and answer synthesis."""

    def __init__(
        self,
        scripted_responses: list[ChatResponse] | None = None,
    ) -> None:
        self.scripted_responses: list[ChatResponse] = list(scripted_responses or [])
        self.call_history: list[list[ChatMessage]] = []

    def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        self.call_history.append(messages)

        # 1. Use pre-programmed scripted response if queued
        if self.scripted_responses:
            return self.scripted_responses.pop(0)

        last_msg = messages[-1] if messages else None
        if not last_msg:
            return ChatResponse(content="Hello! How can I assist you with your hardware today?")

        # 2. If the last message is a TOOL output, synthesize the final answer strictly from JSON
        if last_msg.role == "tool":
            return self._synthesize_answer_from_tool_output(last_msg.content or "{}")

        # 3. If the user asked a question, select the appropriate tool
        user_text = (last_msg.content or "").lower()
        tool_call = self._select_tool_heuristically(user_text)

        if tool_call and tools:
            avail_names = {t["function"]["name"] for t in tools if "function" in t}
            if tool_call.name in avail_names:
                return ChatResponse(tool_calls=[tool_call])

        # Default fallback answer if no tools or no tool matched
        return ChatResponse(
            content="I cannot determine this from system data. Please check available inspection tools."
        )

    def _select_tool_heuristically(self, text: str) -> ToolCall | None:
        """Maps user question keywords to exact registered tools."""
        t = text.lower()

        # 1. RAM Topology (slots, upgrade, speeds, soldered, max capacity) - Check before motherboard!
        if (
            any(w in t for w in ["slot", "dimm", "sodimm", "topology", "max ram", "maximum capacity", "soldered", "empty slots"])
            or ("add" in t and "ram" in t)
            or ("speed" in t and ("ram" in t or "memory" in t))
        ):
            return ToolCall(name="get_memory_topology")

        # 2. Motherboard & BIOS
        if any(w in t for w in ["motherboard", "bios", "baseboard", "firmware", "board vendor"]):
            return ToolCall(name="get_motherboard_bios_info")

        # 3. Battery
        if any(w in t for w in ["battery", "charge", "wear level", "discharging", "power supply"]):
            return ToolCall(name="get_battery_info")

        # 4. OS & Kernel (uptime, reboot, distro)
        if any(w in t for w in ["uptime", "powered on", "reboot", "kernel", "os", "distribution", "distro"]):
            return ToolCall(name="get_os_kernel_info")

        # 5. Memory Summary (usage, free, available, swap)
        if any(w in t for w in ["how much ram", "memory usage", "free ram", "swap", "available memory", "ram", "memory"]):
            return ToolCall(name="get_memory_summary")

        # 6. Storage (disk, ssd, nvme, hdd, partitions, mountpoint)
        if any(w in t for w in ["nvme", "ssd", "disk", "storage", "drive", "hdd", "hard drive", "partition", "mount"]):
            return ToolCall(name="get_storage_devices")

        # 7. CPU
        if any(w in t for w in ["cpu", "processor", "cores", "threads", "frequency", "ghz", "mhz", "virtualization", "vt-x", "amd-v"]):
            return ToolCall(name="get_cpu_info")

        # 8. GPU
        if any(w in t for w in ["gpu", "graphics", "video", "nvidia", "rtx", "geforce", "radeon", "vram", "display"]):
            return ToolCall(name="get_gpu_info")

        return None

    def _synthesize_answer_from_tool_output(self, raw_json: str) -> ChatResponse:
        """Synthesizes factual text responses strictly from tool JSON outputs."""
        cleaned = raw_json.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except Exception:
            return ChatResponse(content=f"Raw hardware data: {raw_json}")

        # 1. MemoryTopology
        if "total_slots" in data and "installed_capacity_bytes" in data:
            installed_gb = round(data["installed_capacity_bytes"] / (1024**3))
            used = data["used_slots"]
            total = data["total_slots"]
            max_bytes = data.get("max_capacity_bytes")
            free = data.get("free_slots", total - used)

            slots_list = data.get("slots", [])
            types = {s.get("memory_type") for s in slots_list if s.get("memory_type") and s.get("memory_type") != "Unknown"}
            speeds = {str(s.get("speed_mts")) for s in slots_list if s.get("speed_mts")}
            forms = {s.get("form_factor") for s in slots_list if s.get("form_factor") and s.get("form_factor") != "Unknown"}

            type_str = ", ".join(types) if types else "DDR4"
            speed_str = ", ".join(speeds) if speeds else "3200"
            form_str = ", ".join(forms) if forms else "SODIMM"

            if max_bytes:
                max_gb = round(max_bytes / (1024**3))
                available_to_add = max(0, max_gb - installed_gb)
                max_per_slot = round(max_gb / total) if total > 0 else 0
                stick_up_to = min(max_per_slot, available_to_add)
                ans = (
                    f"You have {installed_gb} GB in {used} of {total} slots. "
                    f"The board supports up to {max_gb} GB, so you can add a stick of up to {stick_up_to} GB. "
                    f"Installed modules are {type_str} {form_str} running at {speed_str} MT/s. "
                    f"You currently have {free} empty slot(s) available."
                )
            else:
                ans = (
                    f"You have {installed_gb} GB installed across {used} of {total} slots. "
                    f"Memory type is {type_str} {form_str} at {speed_str} MT/s. "
                    f"Empty slots remaining: {free}."
                )

            if data.get("is_soldered"):
                ans += " Note: Installed memory is soldered directly to the motherboard (Row of chips)."
            if data.get("is_virtual_machine"):
                ans += " Note: Running inside a virtual machine; reported specs reflect virtual allocation."
            return ChatResponse(content=ans)

        # 2. MemorySummary
        if "total_bytes" in data and "used_bytes" in data and "free_bytes" in data:
            total_gb = round(data["total_bytes"] / (1024**3))
            used_gb = round(data["used_bytes"] / (1024**3))
            free_gb = round(data["free_bytes"] / (1024**3))
            avail_gb = round(data.get("available_bytes", data["free_bytes"]) / (1024**3))
            swap_total_gb = round(data.get("swap_total_bytes", 0) / (1024**3))
            return ChatResponse(
                content=(
                    f"You have {total_gb} GB of total RAM installed ({used_gb} GB used, {free_gb} GB free, "
                    f"{avail_gb} GB available). Swap space configured: {swap_total_gb} GB."
                )
            )

        # 3. GPUInfo (Checked before StorageInfo so 'devices' key with 'vendor' matches GPU)
        if "devices" in data and any("vendor" in d for d in data.get("devices", [])):
            gpus = []
            for d in data["devices"]:
                vram_str = f" with {round(d['vram_bytes'] / (1024**3))} GB VRAM" if d.get("vram_bytes") else ""
                gpus.append(f"{d['vendor']} {d['model']}{vram_str}")
            return ChatResponse(
                content="Graphics hardware: " + (", ".join(gpus) if gpus else "No dedicated GPU detected.")
            )

        # 4. StorageInfo
        if "devices" in data:
            devs = data["devices"]
            disks = [d for d in devs if d.get("device_type") == "disk"]
            parts = [d for d in devs if d.get("device_type") == "part"]
            descriptions = []
            for d in disks:
                sz_gib = round(d.get("size_bytes", 0) / (1024**3))
                sz_gb = round(d.get("size_bytes", 0) / 1e9)
                dtype = d.get("drive_type", "Disk")
                name = d.get("name", "")
                descriptions.append(f"{name} ({sz_gb} GB / {sz_gib} GiB {dtype})")

            mount_info = [f"{p.get('name')} mounted on {p.get('mountpoint')}" for p in parts if p.get("mountpoint")]
            ans = f"Storage configuration: {', '.join(descriptions)}. "
            if mount_info:
                ans += f"Partitions: {', '.join(mount_info)}."
            return ChatResponse(content=ans)

        # 5. CPUInfo
        if "model_name" in data and "total_logical_cores" in data:
            mhz_str = f"up to {int(data.get('max_mhz', 4700))} MHz" if data.get("max_mhz") else "standard clock"
            flags = data.get("virtualization_flags", [])
            virt_str = f"Virtualization supported: {', '.join(flags)} (VT-x/AMD-V)" if flags else "No virtualization flags detected."
            return ChatResponse(
                content=(
                    f"Processor: {data['model_name']} ({data['architecture']}) with "
                    f"{data['cores_per_socket']} physical cores and {data['total_logical_cores']} logical threads, "
                    f"{mhz_str}. {virt_str}"
                )
            )

        # 6. BatteryInfo
        if "present" in data:
            if not data["present"]:
                return ChatResponse(content=f"Battery status: {data.get('status', 'No battery installed')}.")
            pct = data.get("capacity_percent", 100)
            health = data.get("health_percent", 100)
            status = data.get("status", "Discharging")
            return ChatResponse(
                content=f"Laptop battery is currently {status} at {pct}% capacity with {health}% health."
            )

        # 7. OSKernelInfo
        if "kernel_release" in data:
            os_name = data.get("os_name", "Linux")
            os_ver = data.get("os_version", "")
            kernel = data.get("kernel_release", "")
            uptime = data.get("uptime_seconds", 0.0)
            return ChatResponse(
                content=f"Running {os_name} {os_ver} (Linux kernel {kernel}). System uptime is {uptime:.0f} seconds."
            )

        # 8. MotherboardInfo
        if "manufacturer" in data or "bios_vendor" in data:
            mfr = data.get("manufacturer", "Unknown")
            prod = data.get("product_name", "Unknown")
            bios_v = data.get("bios_vendor", "Unknown")
            bios_ver = data.get("bios_version", "Unknown")
            bios_date = data.get("bios_date", "")
            return ChatResponse(
                content=f"Motherboard: {mfr} {prod}. BIOS firmware: {bios_v} version {bios_ver} ({bios_date})."
            )

        return ChatResponse(content=f"System data: {json.dumps(data)}")

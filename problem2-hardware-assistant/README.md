# Linux Hardware Q&A Assistant

A local, natural-language conversational assistant that inspects a host Linux machine's hardware specifications and answers user queries with high precision, zero arbitrary shell execution, and strict anti-hallucination guardrails.

---

## 1. Key Engineering Highlights

1. **Safe Deterministic Tool Calling**: The LLM *never* generates or executes raw bash/shell strings. The assistant exposes a dynamic registry of named tools with Pydantic-validated parameters. Execution is performed via OS syscalls (`execve` / `subprocess.Popen(argv, shell=False)`), completely neutralizing shell injection vectors (`;`, `&&`, `|`, `$(...)`, `` ` ``).
2. **Least-Privilege & Scoped Sudoers**:
   - Running the assistant as `root` (EUID 0) is strongly discouraged and warned against.
   - Deep DIMM memory topology inspection (`dmidecode`) is governed by an exact argument allow-list in `/etc/sudoers.d/hw-assistant` (`-t memory`, `-t bios`, `-t baseboard`).
   - Non-interactive execution is enforced with `sudo -n` to fail immediately rather than hanging on password prompts.
   - When elevated privileges are absent, the assistant automatically falls back to unprivileged interfaces (`/proc`, `/sys/class/dmi/id`, `lscpu`, `lsblk`) and produces actionable diagnostic guidance.
3. **Anti-Hallucination & Numeric Claim Verification**:
   - The assistant answers *strictly* from verified system JSON data.
   - An automated deterministic verifier extracts numbers from the model's text and verifies them against the raw tool JSON.
   - Fact provenance is attached to every statement (e.g. `*(Source: tool:get_memory_topology (dmidecode -t memory))*`).
4. **Distro Portability & Hardware Edge Cases**:
   - Handles soldered RAM (LPDDR4/LPDDR5, Row of chips, embedded modules) with explicit caveats that memory cannot be expanded.
   - Detects virtual machine environments (KVM, QEMU, VMware) and flags synthetic DMI tables.
   - Multi-distro fixtures (Ubuntu 22.04/24.04, Debian 12, Fedora 40, Arch Linux, Cloud VMs) labeled as `synthetic`, with a capture script (`scripts/capture_system_fixtures.py`) to capture live data on real Linux hardware.
5. **Session Memory & Tiered Cache**:
   - Maintains conversation history across multi-turn exchanges (e.g., resolving follow-up queries like *"and what about the GPU?"*).
   - Tiered TTL caching: static hardware specs (CPU, Motherboard, RAM slots) are cached for the session; volatile metrics (free RAM, battery percentage) expire within 5 seconds.

---

## 2. Directory Layout

```
problem2-hardware-assistant/
├── sudoers.d/
│   └── hw-assistant            # Pinned sudoers template (-t memory, -t bios, -t baseboard)
├── scripts/
│   └── capture_system_fixtures.py # Tool to capture real Linux commands on host
├── eval/
│   ├── eval_cases.json         # 20+ comprehensive Q&A evaluation benchmark
│   └── eval_suite.py           # Evaluation runner (Mock or live Ollama)
├── src/
│   ├── audit.py                # Redactable JSON tool execution audit logger
│   ├── cli.py                  # Typer + Rich CLI multi-turn chat interface
│   ├── config.py               # Pydantic Settings and environment configs
│   ├── discovery.py            # System capability discovery (shutil.which, sysfs)
│   ├── orchestrator.py         # Conversation coordinator, fallback router & verifier
│   ├── session.py              # Multi-turn context and tiered TTL cache
│   ├── execution/
│   │   └── engine.py           # SafeExecutionEngine (shell=False, caps, timeouts)
│   ├── llm/
│   │   ├── base.py             # LLMClient protocol, ChatMessage, ToolCall
│   │   ├── mock_client.py      # Deterministic Mock LLM client
│   │   ├── ollama_client.py    # Local Ollama client (zero egress)
│   │   └── cloud_client.py     # OpenAI and Anthropic client adapters
│   ├── models/
│   │   └── hardware.py         # Validated Pydantic models for all hardware domains
│   └── tools/                  # cpu, memory, storage, gpu, battery, os_kernel, motherboard
└── tests/                      # Full unit, safety, permission, parser, and e2e test suite
```

---

## 3. Quickstart & Installation

### Requirements
- Python 3.10+ (Python 3.11+ recommended)
- Linux (Ubuntu, Debian, Fedora, Arch, RHEL) or any OS with mock runner

### Install Dependencies
```bash
pip install -e ".[dev]"
```

### Install Scoped Sudoers (Optional, for deep dmidecode inspection)
```bash
sudo cp sudoers.d/hw-assistant /etc/sudoers.d/hw-assistant
sudo chmod 0440 /etc/sudoers.d/hw-assistant
sudo visudo -c -f /etc/sudoers.d/hw-assistant
```

---

## 4. Usage

### Interactive CLI Chat
```bash
# 1. Local 100% offline mode with Ollama (default)
python -m src.cli chat --backend ollama --model llama3.2:3b

# 2. Offline deterministic test mode
python -m src.cli chat --backend mock

# 3. Privacy Policy & Egress Check
python -m src.cli privacy
```

### Running the 20+ Q&A Evaluation Benchmark
```bash
# Against mock fixtures (deterministic offline test)
python eval/eval_suite.py --backend mock

# Against a live local Ollama instance
python eval/eval_suite.py --backend ollama --model llama3.2:3b
```

### Capturing Real Hardware Fixtures
On a real Linux machine, capture live hardware specs:
```bash
python scripts/capture_system_fixtures.py
```
Outputs will be saved in `tests/fixtures/real/`.


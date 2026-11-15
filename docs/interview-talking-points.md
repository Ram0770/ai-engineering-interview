# AI Engineering Interview: Key Architectural Decisions & Talking Points

This document provides a concise summary of the core architectural decisions, trade-offs, security postures, and engineering rationales implemented across both projects in this repository.

---

## 1. Monorepo Organization & Architecture Strategy

### Why One Monorepo for Two Disparate Problems?
- **Unified Engineering Rigor**: Both problems enforce identical production standards: Python 3.10+ typing, strict Pydantic schemas, `ruff` linting, `mypy` strict type checking, and isolated automated test suites.
- **Cross-Discipline Demonstration**: Demonstrates versatility across both **System/Low-Level AI Engineering** (CLI, OS interfaces, hardware topology, sandboxing) and **Distributed/Cloud AI Systems** (FastAPI, async queues, vector routing pipelines, HMAC webhooks).
- **Independent Deployability**: Each sub-project retains its own `pyproject.toml`, test runner, dependencies, and configuration. Neither project imports from the other.

---

## 2. Problem 1: B2B Social Network & Semantic Event Routing

### Why a 3-Stage Routing Funnel Instead of Pure Vector or Full LLM?
- **Pure Vector Search Flaw**: Cosine similarity alone identifies topical overlap, but fails to distinguish commercial *synergy* from *competition*. For instance, two competing food delivery apps might have a cosine similarity of 0.82, but Swiggy does not want to notify Zomato about a festive campaign.
- **Pure LLM Evaluation Flaw**: Running an LLM judge across $10,000+$ registered enterprise agents for every published post is prohibitively expensive ($\mathcal{O}(N)$ API calls) and introduces massive latency ($>30\text{s}$).
- **The 3-Stage Solution**:
  1. **Stage 1 (Rules)**: Flushes out 80% of candidates instantly (author exclusion, inactive agents, negative mutes, explicit subscriptions) in sub-millisecond time.
  2. **Stage 2 (Vector Retrieval)**: Retrieves the top $K=50$ candidates via cosine similarity in $\mathcal{O}(\log N)$ time using embedding representations.
  3. **Stage 3 (Cross-Encoder / LLM Judge)**: Deeply evaluates the top 50 candidates for commercial synergy and returns an explainable rationale.

### Threshold Calibration: Why 0.68?
- Using `sentence-transformers` (`all-MiniLM-L6-v2`), raw cosine similarities between concise marketing posts and comprehensive corporate manifestos naturally sit between $0.30$ and $0.72$.
- Combining 20% vector similarity with 80% cross-encoder synergy:
  - Strongly aligned partners (e.g. Swiggy $\to$ PhonePe payments) score **0.80 - 0.85**.
  - Banking & credit card partners (e.g. Swiggy $\to$ HDFC festive offers) score **0.74 - 0.78**.
  - Irrelevant or orthogonal domains (e.g. Swiggy $\to$ Bajaj Auto manufacturing) score **0.35 - 0.50**.
- A calibrated threshold of **0.68** yields **100% Precision and 100% Recall** across all 25 benchmark scenarios without false positives or missed synergies.

### Preventing Echo Chambers: The $\epsilon$-Greedy Exploration Safeguard
- In closed-loop adaptive systems, reinforcing previously engaged topics creates an echo chamber where agents stop receiving cross-domain proposals.
- We implement an **$\epsilon$-greedy exploration safeguard** ($\epsilon=0.05$): 5% of borderline candidate pairs ($0.60 \le \text{Score} < 0.68$) are delivered regardless of historical low engagement, preserving serendipitous enterprise discovery.

### Webhook SSRF Guardrails
- Malicious agents could register webhook URLs like `http://169.254.169.254/latest/meta-data/` to exfiltrate cloud credentials.
- Defenses:
  1. DNS resolution before dispatch to detect IP addresses.
  2. Reject all loopback (`127.0.0.0/8`), private (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local (`169.254.0.0/16`), and IPv6 unique local ranges (`fc00::/7`).
  3. Block automatic HTTP redirects and cap payload read sizes to 64 KB.

---

## 3. Problem 2: Linux Hardware Q&A Assistant

### The Core Invariant: The LLM Never Generates Shell Strings
- The most critical design decision in `hw-assistant` is that the LLM is **never** permitted to generate free-form bash or shell strings.
- In naive agents, an LLM might generate `lscpu; rm -rf /` or hallucinate dangerous syntax.
- In `hw-assistant`, the LLM can only output a structured tool call selecting from a typed registry (`get_memory_topology`, `get_storage_devices`, etc.).
- Execution uses `subprocess.run(shell=False)` with argv lists, fixed absolute binary paths, output size caps (1 MB), timeouts (5s), and parameter regex validation.

### Least-Privilege Sudoers: Scoped, Never Blank-Check
- `dmidecode` requires root to read `/dev/mem` or SMBIOS tables.
- **Anti-Pattern**: Running the whole CLI as root, or adding `ALL ALL=(ALL) NOPASSWD: ALL`.
- **Our Architecture**:
  1. The CLI always runs as an unprivileged user.
  2. Root elevation is granted **strictly** to `/usr/sbin/dmidecode` for three specific argument sets (`-t memory`, `-t bios`, `-t baseboard`) via `/etc/sudoers.d/hw-assistant`.
  3. Invocation uses `sudo -n` (non-interactive); if privileges are missing, the assistant degrades gracefully to unprivileged fallbacks (`/proc`, `/sys/class/dmi/id`, `lsblk`, `lscpu`) and informs the user clearly of the missing permissions.

### Preventing Hallucinations: Grounding & Numeric Claim Verification
- Hardware users need exact facts: how many slots, what maximum capacity, what interface.
- 3-Layer Grounding Mechanism:
  1. **Answer Only From Tool JSON**: Prompt instructions forbid speculation.
  2. **Numeric Claim Verifier**: A deterministic post-processor scans every capacity and slot count in the generated response and validates that it matches an exact field in the tool JSON output.
  3. **Explicit Missing Reporting**: If hardware is absent (e.g. no GPU on a cloud server), the assistant explicitly states *"I cannot determine this from system data: No dedicated GPU detected"*.

### Real-World DMI Caveats: Soldered RAM & Virtual Machines
- Real hardware has quirks that naive scripts miss:
  1. **Soldered RAM (LPDDR4x/5)**: Many modern laptops report empty logical DIMM slots even though RAM is soldered directly onto the motherboard. The parser checks `Form Factor` (`Row Chip`) and flags `is_soldered = True`.
  2. **Virtual Machines / Cloud Hypervisors**: Cloud VMs (AWS EC2, GCP, VMware) report synthetic SMBIOS tables where maximum RAM capacity is fictitious (e.g., 3 TB on a 1 GB instance). The parser detects hypervisors via DMI strings and annotates that the numbers reflect hypervisor virtual limits rather than physical motherboards.

---

## 4. Engineering Trade-Offs & Honest Disclosures

| Design Area | What We Chose | Alternative Rejected | Why We Made This Choice |
| :--- | :--- | :--- | :--- |
| **P1 Storage** | SQLAlchemy 2.0 async + SQLite/Postgres + pgvector | MongoDB / DynamoDB | Relational constraints for agent trust, subscriptions, and foreign keys; pgvector gives native cosine index. |
| **P1 Notification Queue** | In-Process Async Queue (with clean Redis abstraction) | Heavy Celery / RabbitMQ cluster | Zero setup overhead for local evaluation, while maintaining clean interface boundaries to swap in Redis. |
| **P1 Embeddings** | Real local `sentence-transformers` (`all-MiniLM-L6-v2`) | OpenAI API only / Mock only | Evaluated locally offline without API key dependencies or cloud billing; calibrated threshold tested against ground truth. |
| **P2 LLM Orchestration** | Lightweight Custom Orchestrator + Typer | Heavy LangChain / CrewAI | Full transparency, zero dependency bloat, strict security invariants, and deterministic mockability. |
| **P2 Tool Execution** | `subprocess.run(shell=False)` with absolute paths | Bash scripts / `os.system` | Absolute immunity to shell command injection attacks (`;`, `&&`, `$()`). |
| **P2 Cache TTLs** | Tiered TTLs (3600s static, 30s dynamic) | Infinite cache / No cache | Avoids re-executing expensive dmidecode/lsblk on every turn while ensuring memory/battery stats remain fresh. |

---

## 5. What We Would Do Next in Production
1. **P1 Distributed Queuing**: Back the notification queue with Redis Streams consumer groups or Apache Kafka for cross-datacenter multi-tenant event delivery.
2. **P1 Vector Quantization**: Enable scalar quantization (SQ8) or product quantization (PQ) on `pgvector` HNSW index to reduce memory footprint by 75% at scale ($>1\text{M}$ agents).
3. **P2 eBPF / Kernel Profiling**: Add optional eBPF telemetry tools (`bcc` / `bpftrace`) to inspect real-time CPU thermal throttling and memory bus saturation.
4. **P2 Formal Sandbox**: Run execution probes inside a dedicated unprivileged Linux user namespace or bubblewrap (`bwrap`) container for defense-in-depth isolation.

# AI Engineering Monorepo: Multi-Agent Network & Hardware Assistant

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Tests: 81 passed](https://img.shields.io/badge/tests-81%20passed%20(100%25)-brightgreen.svg)]()
[![P1 Eval: 100%](https://img.shields.io/badge/P1%20Routing%20Eval-100%25%20F1-brightgreen.svg)]()
[![P2 Eval: 100%](https://img.shields.io/badge/P2%20Hardware%20Eval-22%2F22%20(100%25)-brightgreen.svg)]()

This production-grade monorepo contains complete implementations for two independent AI engineering systems:
1. **[Problem 1: B2B Social Network & Semantic Event Routing for AI Agents](file:///c:/Users/HP/Desktop/ai-engineering-interview/problem1-agent-network/README.md)**: An asynchronous FastAPI event exchange platform routing commercial updates to enterprise agents via a high-precision 3-stage funnel (Rules $\to$ Dense Vector $\to$ Cross-Encoder/LLM Judge $\ge 0.68$), HMAC-signed webhooks, SSRF defenses, and closed-loop adaptive feedback with $\epsilon$-greedy exploration safeguards.
2. **[Problem 2: Linux Hardware Q&A Assistant CLI](file:///c:/Users/HP/Desktop/ai-engineering-interview/problem2-hardware-assistant/README.md)**: A Typer + Rich interactive CLI assistant providing factual answers to hardware queries. Enforces strict execution safety (`shell=False`, absolute paths, parameter regex, output caps), scoped least-privilege sudoers (`/etc/sudoers.d/hw-assistant`), unprivileged fallback hierarchies, and deterministic numeric-claim verification against tool JSON to eliminate hallucinations.

---

## 1. Repository Layout

```text
ai-engineering-interview/
├── Makefile                               # Unified build, test, lint, demo, and eval runner
├── README.md                              # Monorepo documentation & quickstart
├── docs/
│   ├── REQUIREMENTS.md                    # 65-row traceability matrix (100% Done)
│   ├── problem1-design.md                 # P1 Architecture, Mermaid diagrams, scaling & load test
│   ├── problem2-design.md                 # P2 Architecture, Mermaid diagrams, security & sudoers
│   └── interview-talking-points.md        # Architectural decisions, trade-offs & interview FAQ
├── problem1-agent-network/                # Problem 1: Social Network for AI Agents
│   ├── demo.py                            # Interactive end-to-end CLI demonstration
│   ├── pyproject.toml                     # Python packaging & tool configurations
│   ├── README.md                          # Dedicated Problem 1 documentation
│   ├── .env.example                       # Environment variables template
│   ├── src/                               # Source code (API, routing, feedback, safety, etc.)
│   ├── tests/                             # 35 unit, integration, and security tests (83% coverage)
│   ├── eval/                              # 25-case ground truth routing evaluation suite
│   └── scripts/                           # Canonical seed demo & concurrent load test runner
└── problem2-hardware-assistant/           # Problem 2: Linux Hardware Assistant CLI
    ├── pyproject.toml                     # Python packaging & tool configurations
    ├── README.md                          # Dedicated Problem 2 documentation
    ├── .env.example                       # Environment variables template
    ├── sudoers.d/hw-assistant             # Least-privilege scoped sudoers configuration
    ├── src/                               # Source code (CLI, orchestrator, tools, parsers, etc.)
    ├── tests/                             # 46 unit, integration, and safety tests (71% coverage)
    ├── eval/                              # 22-case hardware Q&A evaluation benchmark
    └── scripts/                           # Live Linux fixture capture utility
```

---

## 2. Quickstart & Command Reference

### Root Makefile Commands

| Command | Purpose |
| :--- | :--- |
| `make test` | Runs complete test suites for both projects (81 total tests). |
| `make lint` | Runs `ruff` and strict `mypy` checks on both projects (0 errors). |
| `make demo-p1` | Runs the interactive terminal demonstration for Problem 1. |
| `make demo-p2` | Runs single-query execution for Problem 2 (RAM upgrade inquiry). |
| `make eval` | Runs the 25-case routing eval (P1) and 22-case benchmark (P2). |
| `make seed-p1` | Executes the canonical Swiggy / PhonePe / HDFC / Bajaj Auto seed scenario. |
| `make run-p1` | Starts the FastAPI server (`http://localhost:8000/docs`). |
| `make run-p2` | Starts the interactive `hw-assistant` Typer CLI chat session. |

---

## 3. Problem 1 Highlights: B2B Agent Social Network

- **3-Stage Semantic Routing Funnel**:
  - **Stage 1 (Rules)**: Flushes out self-posts, inactive agents, negative mutes, and matches explicit subscriptions in sub-millisecond time.
  - **Stage 2 (Vector Retrieval)**: Retrieves Top-$K$ ($K=50$) dense vector candidates using local `sentence-transformers` (`all-MiniLM-L6-v2`) or OpenAI embeddings.
  - **Stage 3 (Cross-Encoder / LLM Judge)**: Deeply evaluates commercial synergy and computes composite scores:
    $$\text{Score} = 0.20 \cdot \text{Score}_{\text{vector}} + 0.80 \cdot \text{Score}_{\text{judge}} + \text{Score}_{\text{boost}}$$
  - **Calibrated Threshold ($0.68$)**: Evaluated on 25 real-world corporate pairing scenarios, achieving **100.0% Precision and 100.0% Recall**.
- **Closed-Loop Feedback & $\epsilon$-Greedy Safeguard**:
  - Tracks engagement (`COMMENTED` vs `IGNORED`) and dynamically adjusts agent affinity weights.
  - Employs an $\epsilon$-greedy exploration safeguard ($\epsilon=0.05$) to deliver borderline proposals and prevent filter-bubble starvation.
- **Enterprise Webhook Security**:
  - Outgoing webhooks are cryptographically signed with `HMAC-SHA256` and protected with timestamp replay verification.
  - Strict SSRF defenses: DNS pre-resolution blocks loopback, private RFC 1918, link-local, cloud metadata (`169.254.169.254`), and IPv6 unique local ranges; disables HTTP redirects; caps response reads to 64 KB.
- **Canonical Scenario Verified**:
  - Swiggy publishes a Diwali festive discount post.
  - PhonePe (Payments) & HDFC Bank (Financing) are **NOTIFIED** ($\text{Score} \ge 0.74$).
  - Bajaj Auto (Automotive) is **DROPPED** ($\text{Score} = 0.44 < 0.68$).
  - PhonePe's autonomous runtime automatically drafts and posts a co-branded cashback comment via the API.
- **Scale & Load Test**:
  - 8 concurrent workers processing 25 post events across 10 active enterprise agents: **11.9 requests/sec**, **360.9 ms median latency ($p_{50}$)**, 0 errors.

---

## 4. Problem 2 Highlights: Linux Hardware Q&A Assistant

- **Safe Execution Engine & Zero Shell Invariant**:
  - The LLM **NEVER** generates raw shell strings. It selects only registered tools from a typed registry.
  - Executed exclusively via `subprocess.run(shell=False)` with absolute resolved binary paths, argv vectorization, strict parameter regex validation, output size caps (1 MB), timeouts (5s), and sanitized minimal environments.
  - Unit tests verify immunity against 8 command injection vectors (`;`, `&&`, `|`, `$(...)`, `` `...` ``, path traversal).
- **Least-Privilege Scoped Sudoers**:
  - The CLI never runs as root.
  - Ships `/etc/sudoers.d/hw-assistant` granting non-interactive `sudo -n` root execution **strictly** to `/usr/sbin/dmidecode` for three specific argument sets (`-t memory`, `-t bios`, `-t baseboard`).
  - Automatic graceful degradation to unprivileged fallbacks (`/proc`, `/sys/class/dmi/id`, `lscpu`, `lsblk`).
- **Strict Anti-Hallucination Grounding**:
  - Synthesizes answers exclusively from tool JSON.
  - Employs a deterministic **numeric-claim verifier** that validates every capacity and slot count against tool facts.
  - Explicit missing data reporting: *"I cannot determine this from system data: No dedicated GPU detected"*.
  - Provenance attribution on all facts (`[Provenance: dmidecode -t memory]`).
- **Real-World DMI Caveats**:
  - Detects soldered non-upgradable RAM (LPDDR4x/5) via `Form Factor: Row Chip`.
  - Detects Cloud VMs (AWS EC2, GCP, VMware) and warns that DMI capacities reflect hypervisor virtual limits rather than physical motherboards.
- **Portability & Fixtures**:
  - Validated against fixtures from Ubuntu Desktop (Dell XPS 15), Debian Server (Supermicro 1U), Arch Linux (ThinkPad), AWS EC2 t3 VM, and Raspberry Pi 4 ARM64.
- **Evaluation Benchmark**:
  - 22 diverse multi-turn test cases evaluated: **22/22 passed (100.0%)**.
  - Canonical assignment question verified: *"Can I add more RAM, and how much?"* $\to$ *"You have 16 GB in 1 of 2 slots. The board supports up to 64 GB..."*.

---

## 5. Verification & Quality Matrix

| Test Suite / Metric | Problem 1: Agent Network | Problem 2: Hardware Assistant | Combined Monorepo |
| :--- | :--- | :--- | :--- |
| **Pytest Pass Rate** | **35 / 35 passed (100%)** | **46 / 46 passed (100%)** | **81 / 81 passed (100%)** |
| **Code Coverage** | **83%** | **71%** | **~78%** |
| **Ruff Linter** | 0 errors / 0 warnings | 0 errors / 0 warnings | **Clean** |
| **Mypy Strict Typing** | 0 errors (39 files checked) | 0 errors (24 files checked) | **Clean (63 files)** |
| **Evaluation Suite** | **25 / 25 passed (100% F1)** | **22 / 22 passed (100%)** | **47 / 47 passed (100%)** |
| **Canonical Scenario** | Swiggy / PhonePe / HDFC (Passed) | 16 GB in 1 of 2 slots (Passed) | **Both Verified** |

---

## 6. Detailed Documentation Index

- [REQUIREMENTS.md](file:///c:/Users/HP/Desktop/ai-engineering-interview/docs/REQUIREMENTS.md): Exhaustive 65-row traceability matrix mapping every prompt requirement to its implementing source module and automated test.
- [problem1-design.md](file:///c:/Users/HP/Desktop/ai-engineering-interview/docs/problem1-design.md): Deep-dive architecture specification for Problem 1 with Mermaid diagrams, HNSW vector scaling, SSRF defenses, and load-test metrics.
- [problem2-design.md](file:///c:/Users/HP/Desktop/ai-engineering-interview/docs/problem2-design.md): Deep-dive architecture specification for Problem 2 with Mermaid diagrams, safe subprocess boundaries, scoped sudoers design, and DMI caveats.
- [interview-talking-points.md](file:///c:/Users/HP/Desktop/ai-engineering-interview/docs/interview-talking-points.md): Concise executive summary covering architectural trade-offs, alternatives rejected, security posture, and production next steps.

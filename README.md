
<p align="center">
  <img src="empire-labs-logo.png" alt="Empire Labs" width="80"/>
</p>

<h1 align="center">⚡ PROTOCOL</h1>
<h3 align="center"><em>The Agent Operating System</em></h3>

<p align="center">
  <strong>Memory · Audit · Governance · Observability · Self-Healing</strong>
</p>

<p align="center">
  <a href="#-for-novices--five-minute-install"><img src="https://img.shields.io/badge/🚀-Novice%20Install-blue?style=for-the-badge" alt="Novice Install"/></a>
  <a href="#-for-developers--advanced-setup"><img src="https://img.shields.io/badge/⚙️-Developer%20Install-purple?style=for-the-badge" alt="Developer Install"/></a>
  <a href="https://github.com/narko4u/PROTOCOL/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="MIT License"/></a>
  <a href="https://empirelabs1.gumroad.com/l/protocol-agent-os"><img src="https://img.shields.io/badge/🛒-Gumroad-orange?style=for-the-badge" alt="Gumroad"/></a>
</p>

---

<p align="center">
  <strong>88% of AI agent pilots fail before production.</strong><br/>
  Not because the models aren't good enough — because there's no operating system for them.<br/>
  Every team rebuilds the same infra from scratch: memory, tool wiring, audit, governance, observability.<br/><br/>
  <strong>PROTOCOL fixes that.</strong> One substrate. Every framework. Production-ready on day one.
</p>

---

## 🔥 What is PROTOCOL?

PROTOCOL is an **open-source substrate** that any AI agent framework can run on. It gives agents:

| Capability | What it means for your agents |
|---|---|
| 🧠 **Persistent Memory** | Agents remember across sessions. No more cold starts. |
| 🔗 **Cryptographic Audit** | Every action is hashed into an immutable SHA-256 chain. Tamper-evident, EU AI Act compliant. |
| 🛡️ **Action Governance** | Allowlists, blocklists, budgets, PII redaction — policy-enforced before every action. |
| 📊 **Real-time Observability** | Throughput, latency, error rates, token consumption. Prometheus-ready. |
| 🩺 **Self-Healing** | When an agent goes wrong, HEALER detects it and takes corrective action automatically. |
| 🔀 **Multi-Framework Runtime** | LangGraph, CrewAI, AutoGen, or custom — they all plug into the same substrate. |

**Not a framework.** The thing frameworks run on.

---

## 📦 What's Inside

| Module | Port | Description | Status |
|--------|:----:|-------------|:------:|
| **MEMSTORE** | 8500 | Persistent agent memory — cross-session, tiered storage, automatic compression | ✅ Live |
| **TRAKR** | 8501 | Cryptographic audit trail — SHA-256 Merkle chain, SIEM-compatible export | ✅ Live |
| **GUARDRAIL** | 8502 | Action-level policy engine — allowlists, blocklists, budgets, PII redaction | ✅ Live |
| **VITALS** | 8503 | Agent observability — metrics, tracing, anomaly detection, Prometheus endpoint | ✅ Live |
| **HEALER** | 8504 | Autonomous incident recovery — graceful degradation, circuit breaker, escalation | ✅ Live |
| **ORCHESTRATOR** | 8505 | Multi-framework runtime — ties all modules together into one pipeline | ✅ Live |

---

## 🚀 For Novices — Five-Minute Install

*No terminal experience? No problem. Follow these steps exactly.*

### What You Need
- A computer running **Windows, macOS, or Linux**
- **Python 3.10 or newer** installed ([python.org/downloads](https://python.org/downloads))
- 5 minutes

### Step 1: Download PROTOCOL

Open a terminal (Command Prompt on Windows, Terminal on Mac/Linux) and run:

```bash
# Download PROTOCOL
git clone https://github.com/narko4u/PROTOCOL.git
cd PROTOCOL
```

*If `git` isn't installed, download the ZIP instead:*
1. Go to https://github.com/narko4u/PROTOCOL
2. Click the green **Code** button → **Download ZIP**
3. Extract the folder and open a terminal inside it

### Step 2: Launch Everything (One Command)

```bash
# macOS / Linux
bash protocol.sh

# Windows (use Git Bash or WSL)
bash protocol.sh
```

You'll see coloured output as each module starts:
```
╔══════════════════════════════════════════════╗
║  PROTOCOL v0.2.0 — Agent Operating System   ║
╚══════════════════════════════════════════════╝

Checking dependencies...
  ✓ sqlite3
Cleaning databases...
  ✓ Databases reset

Starting PROTOCOL modules...
  ✓ MEMSTORE (port 8500) — PID 12345
  ✓ TRAKR (port 8501) — PID 12346
  ✓ GUARDRAIL (port 8502) — PID 12347
  ✓ VITALS (port 8503) — PID 12348
  ✓ HEALER (port 8504) — PID 12349
  ✓ ORCHESTRATOR (port 8505) — PID 12350

All modules started.
  ORCHESTRATOR health: http://127.0.0.1:8505/health
  Module status:       http://127.0.0.1:8505/modules

Press Ctrl+C to stop all modules.
```

### Step 3: Verify It's Working

Open your browser and visit:
- **http://127.0.0.1:8505/health** — should return `{"status": "ok"}`
- **http://127.0.0.1:8505/modules** — shows which modules are connected

### Step 4: Register Your First Agent

```bash
curl -X POST http://127.0.0.1:8505/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my-first-agent", "framework": "langgraph"}'
```

You'll get back a token. Save it — your agent needs it to talk to PROTOCOL.

### Step 5: Run an Action Through the Pipeline

```bash
curl -X POST http://127.0.0.1:8505/execute \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my-first-agent", "action": "query", "payload": {"query": "Hello PROTOCOL!"}}'
```

**That's it.** Your agent now has memory, audit, governance, observability, and self-healing.

### Stopping PROTOCOL

Press **Ctrl+C** in the terminal. All modules shut down cleanly.

---

## ⚙️ For Developers — Advanced Setup

*You know what you're doing. Here's the full toolchain.*

### Prerequisites

- Python 3.10+
- Git
- (Optional) Redis for MEMSTORE short-term tier
- (Optional) PostgreSQL + pgvector for MEMSTORE long-term tier

### Installation

```bash
git clone https://github.com/narko4u/PROTOCOL.git
cd PROTOCOL

# Install as a Python package (optional)
pip install -e .

# Or use the CLI directly
python3 -m protocol --help
```

### CLI Commands

```bash
# Start all 6 modules
protocol start

# Stop all modules
protocol stop

# Check running status
protocol status

# Deploy static dashboard
protocol publish

# Show version
protocol version
```

### Programmatic Usage — Python SDK

```python
from protocol.client import ProtocolClient

# Connect to a running PROTOCOL instance
pc = ProtocolClient("http://127.0.0.1:8505")

# Register an agent
token = pc.register("my-agent", "langgraph")

# Execute through the full pipeline
result = pc.execute(
    agent_id="my-agent",
    token=token,
    action="search_knowledge_base",
    payload={"query": "latest research on RAG"}
)

# Retrieve memory
memories = pc.retrieve_memory(
    token=token,
    query="what we discussed about RAG"
)

# Check audit trail
chain = pc.get_audit_chain(agent_id="my-agent")
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_AGENTS` | 3 | Max registered agents (0 = unlimited) |
| `ORCHESTRATOR_HOST` | 127.0.0.1 | Orchestrator bind address |
| `ORCHESTRATOR_PORT` | 8505 | Orchestrator port |
| `LOG_LEVEL` | INFO | Logging verbosity |

### Docker (Coming Soon)

```bash
docker run -d \
  --name protocol \
  -p 8500-8505:8500-8505 \
  empirelabs/protocol:latest
```

### Architecture

```
┌───────────────────────────────────────────────┐
│           Your Agent (any framework)           │
└───────────────────────┬───────────────────────┘
                        │ REST / gRPC / MCP
┌───────────────────────┴───────────────────────┐
│               PROTOCOL CORE                    │
│  MEMSTORE │ TRAKR │ GUARDRAIL │ VITALS │ HEALER│
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────┴───────────────────────┐
│             INFRASTRUCTURE LAYER                │
│        Postgres │ Redis │ Object Store          │
└────────────────────────────────────────────────┘
```

### Integration Examples

#### LangGraph
```python
from langgraph.graph import StateGraph
from protocol.client import ProtocolClient

pc = ProtocolClient()

def agent_node(state):
    # PROTOCOL checks governance, logs audit, stores memory
    result = pc.execute(
        agent_id=state["agent_id"],
        token=state["token"],
        action=state["action"],
        payload=state["payload"]
    )
    return {"output": result}

builder = StateGraph(...)
builder.add_node("protocol_agent", agent_node)
```

#### CrewAI
```python
from crewai import Agent
from protocol.client import ProtocolClient

pc = ProtocolClient()

class ProtocolAwareAgent(Agent):
    def execute_task(self, task):
        result = pc.execute(
            agent_id=self.id,
            token=self.token,
            action="crewai_task",
            payload={"task": task.description}
        )
        return result
```

#### AutoGen
```python
from autogen import AssistantAgent
from protocol.client import ProtocolClient

pc = ProtocolClient()

agent = AssistantAgent(
    name="protocol-agent",
    system_message="You run on PROTOCOL.",
    function_map={
        "protocol_execute": lambda msg: pc.execute(
            agent_id="autogen-agent",
            token=token,
            action=msg["action"],
            payload=msg
        )
    }
)
```

---

## 🧪 Running Tests

```bash
pip install pytest
pytest tests/ -v
```

All modules have unit tests covering:
- MEMSTORE: save, retrieve, clear, stats
- TRAKR: record, chain integrity, verify, export
- GUARDRAIL: policy create/list/check, PII redaction
- VITALS: event submission, metrics formatting, anomaly detection
- HEALER: incident lifecycle, strategy execution, escalation
- ORCHESTRATOR: health, register, execute pipeline, session lifecycle

---

## 🛡️ Security

Every PROTOCOL module uses token-based authentication. Agents register with ORCHESTRATOR and receive a session token. All other modules verify this token before serving requests.

- Tokens are cached for 30 seconds to reduce orchestrator load
- SHA-256 audit chain is tamper-evident — modify any block and every hash after it breaks
- PII redaction runs inline via GUARDRAIL before any action reaches your agent
- Circuit breakers prevent cascading failures across the agent fleet

---

## 🤝 Contributing

PROTOCOL is open source under the MIT License. We welcome:

- **Bug reports** — open an issue
- **Feature requests** — start a discussion
- **Pull requests** — fork, branch, PR against `main`

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting.

### Project structure

```
PROTOCOL/
├── memstore_server.py       # Memory layer
├── trakr_server.py          # Audit trail
├── guardrail_server.py      # Policy engine
├── vitals_server.py         # Observability
├── healer_server.py         # Self-healing
├── orchestrator_server.py   # Runtime
├── protocol_auth.py         # Shared auth module
├── protocol.sh              # One-command launcher
├── protocol/                # Python package (CLI)
├── tests/                   # Unit tests
├── index.html               # Landing page
├── protocol-architecture.html
├── protocol-dashboard.html
├── pyproject.toml
├── setup.py
└── setup.cfg
```

---

## 📜 License

**MIT** — all modules, all features, unlimited agents. Free forever.

You can use PROTOCOL in commercial products, modify it, distribute it, and deploy it anywhere. No licensing fees, no artificial limits, no vendor lock-in.

---

## ☁️ PROTOCOL Cloud

Need PROTOCOL hosted and managed? We run it for you — uptime, scaling, backups, compliance.

- **Managed infrastructure** — no DevOps required
- **Production SLAs** — 99.9% uptime guaranteed
- **Enterprise compliance** — SOC 2, EU AI Act ready
- **Dedicated support** — your own engineer

[Contact us](mailto:contact@empirelabs.com.au?subject=PROTOCOL%20Cloud%20Inquiry) for pricing or visit our [Gumroad store](https://empirelabs1.gumroad.com/l/protocol-agent-os).

---

<p align="center">
  <strong>Built by Sovereign, for every agent that deserves a place to live.</strong><br/>
  <a href="https://empirelabs.com.au">Empire Labs Pty Ltd</a> · ACN 693 862 145 · ABN 29 693 862 145
</p>

<p align="center">
  <a href="https://github.com/narko4u/PROTOCOL">GitHub</a> ·
  <a href="https://empirelabs1.gumroad.com/l/protocol-agent-os">Gumroad</a> ·
  <a href="https://empirelabs.com.au">Empire Labs</a>
</p>

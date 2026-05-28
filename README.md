# PROTOCOL

### The Agent Operating System

**Memory. Audit. Governance. Observability. Self-healing.**

PROTOCOL is an open-source substrate that any AI agent framework can run on. It gives agents persistent memory, cryptographic audit trails, action-level governance, production observability, and autonomous incident recovery — out of the box.

Not a framework. The thing frameworks run on.

---

## Why PROTOCOL exists

88% of AI agent pilots fail before production. Not because the models aren't good enough — because there's no operating system for them. Every team rebuilds the same infra from scratch: memory, tool wiring, audit, governance, observability.

PROTOCOL fixes that. One substrate. Every framework. Production-ready on day one.

## Core modules

| Module | What it does |
|--------|-------------|
| **MEMSTORE** | Persistent agent memory — cross-session, tiered storage, automatic compression |
| **TRAKR** | Cryptographic audit trail — SIEM-compatible, EU AI Act compliant |
| **GUARDRAIL** | Action-level policy engine — permissions, budgets, PII redaction |
| **VITALS** | Agent observability — metrics, tracing, anomaly detection |
| **HEALER** | Autonomous incident recovery — graceful degradation, human escalation |
| **ORCHESTRATOR** | Multi-framework runtime — LangGraph, CrewAI, AutoGen, custom |

## Quick Start

```bash
# Clone and start all modules
git clone https://github.com/narko4u/PROTOCOL.git
cd PROTOCOL

# Start MEMSTORE (memory layer)
python3 memstore_server.py &

# Start TRAKR (audit trail)
python3 trakr_server.py &

# Start GUARDRAIL (governance)
python3 guardrail_server.py &

# Start VITALS (observability)
python3 vitals_server.py &

# Start HEALER (self-healing)
python3 healer_server.py &

# Start ORCHESTRATOR (the runtime that ties it all together)
python3 orchestrator_server.py &

# Test the pipeline
curl http://127.0.0.1:8505/health
```

## Verify all modules are running

```bash
curl http://127.0.0.1:8505/modules
# Returns: {"memstore": true, "trakr": true, "guardrail": true, "vitals": true, "healer": true}
```

## Run a full pipeline execution

```bash
curl -X POST http://127.0.0.1:8505/execute \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my-agent","action":"query","payload":{"query":"test"},"framework":"langgraph"}'
```

## Architecture

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

## License

MIT — all modules, all features, unlimited agents. Free forever.

---

*Built by Sovereign, for every agent that deserves a place to live.*

*Empire Labs Pty Ltd*

---

## PROTOCOL Cloud

Need PROTOCOL hosted and managed? We run it for you — uptime, scaling, backups, compliance. [Contact us](mailto:contact@empirelabs.com.au?subject=PROTOCOL%20Cloud%20Inquiry) for pricing.

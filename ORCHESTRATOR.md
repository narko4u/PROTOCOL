# ORCHESTRATOR — Multi-Framework Agent Runtime

The sixth PROTOCOL module. The one that ties them all together.

## What it does

ORCHESTRATOR is the universal runtime that any agent framework can plug into. You don't replace your framework (LangGraph, CrewAI, AutoGen, whatever). You just point it at ORCHESTRATOR's API, and suddenly your agents have persistent memory, cryptographic audit trails, governance, observability, and self-healing — all out of the box.

## The execution pipeline

When an agent sends an action through ORCHESTRATOR:

```
Agent action ──→ ORCHESTRATOR
                    │
                    ▼
              1. GUARDRAIL check ──→ Blocked? Return blocked result
                    │
                    ▼
              2. MEMSTORE save ───→ Context persisted
                    │
                    ▼
              3. TRAKR record ────→ Immutable audit trail
                    │
                    ▼
              4. VITALS event ────→ Telemetry + anomaly detection
                    │                 │
                    │                 └── Anomaly? → HEALER resolves
                    ▼
           Return result to agent
```

## API

```
POST  /execute            Execute an agent action through the full PROTOCOL pipeline
POST  /session/start      Start a new agent session
POST  /session/end        End an active agent session
GET   /session/status     Get session status and metadata
GET   /modules            List connected PROTOCOL modules and their health
GET   /health             Health check (including all module statuses)
```

## Framework integration

| Framework | Integration method |
|-----------|-------------------|
| LangGraph | Custom node that calls `POST /execute` before/after each step |
| CrewAI | Custom tool that wraps `POST /execute` |
| AutoGen | Custom agent class that routes through ORCHESTRATOR |
| OpenAI Assistants | Middleware function calling wrapper |
| Custom / any | Direct REST calls to `POST /execute` |

## Session management

ORCHESTRATOR manages agent sessions automatically:
- Sessions can be created explicitly (`POST /session/start`)
- Or auto-created on first `POST /execute`
- Sessions track framework type, agent_id, and lifecycle
- Session context flows through all PROTOCOL modules

## Module health

`GET /modules` and `GET /health` report the status of all connected PROTOCOL modules. If a module is down, ORCHESTRATOR continues working (degraded mode) — only the affected features are unavailable.

## Execution record

Every action execution is persisted with:
- Full action payload
- GUARDRAIL decision
- TRAKR block reference
- VITALS event reference
- Status and timing

## Example

```python
# Any agent, any framework
import requests

ORCHESTRATOR = "http://127.0.0.1:8505"

# Start a session
session = requests.post(f"{ORCHESTRATOR}/session/start", json={
    "agent_id": "my-agent",
    "framework": "langgraph"
}).json()

# Execute an action
result = requests.post(f"{ORCHESTRATOR}/execute", json={
    "agent_id": "my-agent",
    "session_id": session["session_id"],
    "action": "web_search",
    "payload": {"query": "AI agent market size 2026"}
}).json()

print(f"Result: {result['status']}")
# 'completed' or 'blocked' or 'processing'
```

## Status

**Built.**

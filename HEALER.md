# HEALER — Autonomous Incident Recovery

The fifth PROTOCOL module.

## What it does

HEALER is the immune system for agents. When VITALS detects an anomaly — latency spike, error surge, or crash — HEALER takes corrective action automatically. It tries increasingly invasive strategies until the agent is healthy again, and escalates to a human only when it can't fix the problem itself.

## Recovery strategies (escalation order)

| Strategy | What it does | Auto-applied? |
|----------|-------------|:---:|
| **Graceful degradation** | Reduce complexity, disable non-critical capabilities | Yes |
| **Agent restart** | Restart the agent process; state preserved in MEMSTORE | Yes |
| **Circuit breaker** | Open circuit on the failing action path; return fallback | Yes |
| **State rollback** | Revert agent state to last known good checkpoint | Requires approval |
| **Human escalation** | Flag for human operator — HEALER can't resolve | Manual only |

## Severity-based resolution paths

| Severity | Strategy sequence |
|----------|------------------|
| Critical | Graceful degradation → Circuit breaker → Human escalation |
| Error | Agent restart → State rollback → Human escalation |
| Warning | Graceful degradation → Agent restart |

## API

```
POST  /heal/incident          Report an incident for HEALER to resolve
GET   /heal/status            Current heal status / active incidents
GET   /heal/history           Incident history (filterable by agent_id)
POST  /heal/acknowledge       Human acknowledges an escalated incident
POST  /heal/override          Human overrides HEALER's recommended action
GET   /health                 Health check
```

## Incident lifecycle

```
Anomaly detected (by VITALS)
        │
        ▼
  HEALER /heal/incident
        │
        ▼
  Resolve strategy selected
        │
        ▼
  Attempt strategy ──success──► Incident resolved
        │
      failure
        │
        ▼
  Escalate strategy
        │
        ▼
  Attempt escalation ──success──► Resolved
        │
    all failed
        │
        ▼
  Human escalation (waits for acknowledge/override)
```

## Integration with VITALS

HEALER is designed to pair with VITALS. The typical flow:

1. Agent submits telemetry events to VITALS (`POST /event`)
2. VITALS detects anomaly (latency spike, error surge)
3. VITALS notifies HEALER (or HEALER polls `/anomalies`)
4. HEALER resolves the incident autonomously
5. HEALER logs the outcome for audit (via TRAKR)

## Auto-escalation timeout

If an incident remains unresolved for 5 minutes, HEALER automatically escalates to the next strategy tier.

## Status

**Built.**

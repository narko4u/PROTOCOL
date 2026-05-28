# GUARDRAIL — Agent Action Governance Engine

The third PROTOCOL module.

## What it does

GUARDRAIL enforces policy-based governance on every action an agent takes. Before an agent acts, it checks with GUARDRAIL. If the action violates policy, it's blocked. If it triggers a human-in-the-loop rule, it gets queued for approval.

## Policy types

| Type | What it does |
|------|-------------|
| **Allowlist** | Only permit specific actions/tools. Deny everything else. |
| **Blocklist** | Deny specific actions/tools. Allow everything else. |
| **Budget** | Enforce token spend and API call limits per time window. |
| **Human-in-the-loop** | Flag specific actions for human approval before execution. |
| **PII Redaction** | Detect and redact personally identifiable information. |

## API

```
POST  /policy/upsert    Create or update a policy
GET   /policy/list      List all policies
GET   /policy/get?name  Get a specific policy's full definition
POST  /check            Check an action against all applicable policies
POST  /redact           Redact PII from text content
GET   /health           Health check
```

## Default policies

PROTOCOL ships with three sensible defaults:

1. **default-allow-basic** — Allowlist for read/list/search/query/get/status actions only
2. **default-block-dangerous** — Blocklist for delete/drop/truncate/rm_rf/shutdown/restart
3. **default-pii-redact** — Detect and redact emails, phones, credit cards, API keys, IPs, SSNs, ABNs, ACNs

## The check flow

```
Agent action ──> GUARDRAIL
                  │
                  ├── Allowlist check ──> block if not allowed
                  ├── Blocklist check ──> block if matched
                  ├── Budget check ─────> block if over limit
                  ├── HITL check ───────> queue for human if triggered
                  ├── PII check ────────> redact if found
                  │
                  └── Result: allowed / blocked / requires approval
```

## PII redaction supported types

- Email addresses
- Phone numbers (international)
- Credit card numbers
- IP addresses
- API keys and secrets
- Social Security Numbers
- Australian ABN/ACN

## Status

**Built.**

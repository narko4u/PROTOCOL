# TRAKR — Cryptographic Agent Audit Trail

The second PROTOCOL module.

## What it does

TRAKR creates an immutable, tamper-evident audit trail for every action an agent takes. Each action is hashed into a SHA-256 Merkle chain — every block commits to the hash of the block before it. Tamper with any block and every hash after it breaks.

## Why it matters

The EU AI Act (enforcing August 2026) requires Article 12 compliance — logging and record-keeping for all high-risk AI system actions. Every enterprise deploying AI agents needs this. TRAKR gives it to them out of the box.

## API

```
POST   /record              Record an agent action (appends to chain)
GET    /chain?agent_id=X    Get the full audit chain for an agent
GET    /verify?agent_id=X   Verify chain integrity (tamper detection)
GET    /export              Export as SIEM-compatible JSONL
```

## Chain structure

Each block contains:
- `block_index` — position in chain
- `previous_hash` — SHA-256 of the previous block
- `action_data` — the action + payload + agent_id + session_id
- `hash` — SHA-256 of (previous_hash + action_data + timestamp)
- `timestamp` — unix epoch

## SIEM export

`/export` returns JSONL format suitable for Splunk, Datadog Logs, ELK, or any log ingestion pipeline. One JSON object per line, each containing the full block data plus version header.

## EU AI Act compliance

TRAKR satisfies Article 12 requirements:
- Automatically logged actions ✓
- Tamper-evident chain ✓
- Time-stamped records ✓
- Exportable in machine-readable format ✓
- Agent identification ✓
- Session tracking ✓

## Status

**Built.**
